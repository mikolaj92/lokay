import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { BACKGROUND_CONTEXT as context } from "@earendil-works/chord/context";
import { createModels, createProvider } from "@earendil-works/pi-ai/models";
import { builtinProviders } from "@earendil-works/pi-ai/providers/all";
import { stream, streamSimple } from "@earendil-works/pi-ai/api/openai-completions";
import { AssistantEntry, createRegistry, Harness } from "@earendil-works/pi-durable";
import { NodeExecutionEnv } from "@earendil-works/pi-durable/env/node";
import { CodingTools } from "@earendil-works/pi-durable/tools";
import { openNodeSqliteStorage } from "@earendil-works/pi-durable/storage/sqlite/node";

const [database, sessionId, requestId, provider, modelId, prompt] = process.argv.slice(2);
if (![database, sessionId, requestId, provider, modelId, prompt].every(Boolean)) {
    throw new Error("Missing durable execution context");
}
const models = createModels();
for (const provider of builtinProviders()) models.setProvider(provider);
if (process.env.LOKAY2_PI_BASE_URL) {
    models.setProvider(createProvider({
        id: provider,
        baseUrl: process.env.LOKAY2_PI_BASE_URL,
        auth: { apiKey: {
            name: "Lokay durable provider",
            resolve: async () => ({ auth: { apiKey: process.env.LOKAY2_PI_API_KEY || "local" } }),
        } },
        models: [{
            id: modelId, provider, baseUrl: process.env.LOKAY2_PI_BASE_URL,
            name: modelId, api: "openai-completions", reasoning: false,
            input: ["text"], contextWindow: 128000, maxTokens: 16384,
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        }],
        api: { stream, streamSimple },
    }));
}
if (!models.getModel(provider, modelId)) throw new Error("Unknown durable model; configure LOKAY2_PI_BASE_URL for a custom provider");
const registry = createRegistry();
registry.install(CodingTools);
await mkdir(dirname(database), { recursive: true });
const harness = await Harness.open(await openNodeSqliteStorage(database), {
    models, registry,
    env: ({ cwd }) => new NodeExecutionEnv({ cwd: cwd || process.cwd() }),
}, context);
try {
    const root = await harness.root(context, { agent: {
        model: { provider, modelId }, cwd: process.cwd(),
        instructions: "Use read, write, edit and bash to complete the request. Never push, create PRs or merge. Do not add code comments, docstrings or unit tests.",
    } });
    console.error(JSON.stringify({ sessionId, conversationId: root.id, requestId }));
    harness.resume();
    const submission = await root.submit({ type: "input", content: prompt, requestId }, context);
    console.error(JSON.stringify({ sessionId, submissionId: submission.id }));
    const settled = await submission.wait(context);
    if (settled.status !== "done" || settled.type !== "input") {
        console.error(JSON.stringify(settled));
        process.exitCode = 1;
    } else {
        const answer = await root.commit((tx) => tx.entry(AssistantEntry, settled.answer), context);
        for (const message of answer?.model || []) {
            for (const block of message.content || []) {
                if (block.type === "text") process.stdout.write(block.text + "\n");
            }
        }
    }
} finally {
    await harness.close(context);
}
