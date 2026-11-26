# Language Learning LINE Chatbot — Specification Draft

Version: 0.11  
Updated: 2026-11-25 (Asia/Taipei)  
Status: The first local use case, `CheckSentence`, is implemented and tested with a fake evaluator.

## 0. Learning goal and collaboration

Confirmed primary engineering goal: the owner gains experience starting a system from scratch. The owner initializes the project and defines the domain and use cases. The assistant guides and reviews those decisions, then implements the agreed design.

### Ownership

| Work | Owner's responsibility | Assistant's responsibility |
| --- | --- | --- |
| Requirements and scope | Describe behavior, priorities, inputs, outputs, and rules | Ask focused questions, identify gaps, and explain trade-offs |
| Domain design | Identify concepts, relationships, invariants, and necessary state | Review the reasoning and offer feedback after the owner's first attempt |
| Application design | Define use cases, contracts, and required external capabilities | Review boundaries and failure behavior; help derive interfaces |
| Project initialization | Create the repository, environment, package configuration, and initial structure | Explain choices and provide step-by-step instructions |
| Implementation | Review whether code matches the intended design | Implement agreed domain/use-case logic, adapters, wiring, and appropriate tests |
| Integration and deployment | Choose configuration and operating behavior with guidance | Implement integration, verify behavior, and explain observed results |

### Working method

- Give one concrete exercise at a time, with a small, reviewable outcome.
- Ask for the owner's first attempt before supplying a complete domain model or use-case design.
- Explain the purpose of each step and teach only the concepts needed for that step.
- Review the owner's reasoning before moving to the next step.
- Implement a small agreed flow, then explain the code and validate it against the owner's requirements.
- Keep design decisions and unresolved questions explicit.
- Treat earlier assistant-authored entities, ports, field names, and infrastructure choices below as reference proposals. They do not prescribe the owner's design.
- Work through Reply Bot and Tutorial Bot in small slices. Translation and explanation remains the proposed first design exercise.

### Learning sequence

1. Describe the inputs, outputs, rules, and failure behavior for one slice of Reply Bot or Tutorial Bot.
2. Derive domain concepts and application use cases from the owner's description, then define the contracts needed for that slice.
3. Let the owner initialize the repository and Python project using guided instructions.
4. Implement and verify the agreed slice incrementally.
5. Repeat for the other flow, then address session context, integrations, and deployment.

Current step: 4 for the first sentence-feedback slice. `CheckSentence` accepts a configurable target language and tutorial language. The broader Tutorial Bot and Reply Bot contracts remain to be defined incrementally.

### Owner's first requirements draft — 2026-10-04

This table records the owner's first requirements draft. Section 1 records subsequent decisions.

| Area | Owner-defined requirement | Open item |
| --- | --- | --- |
| Goals | Translate into Japanese with vocabulary and grammar explanations; generate a suitable conversation reply based on intent | Reply intent is collected through clarification when needed; see section 4 |
| Required input | The sentence to translate or respond to. The user can state the reply intent up front or answer a clarification. | — |
| Optional input | A desired translation/explanation format is a candidate | Which preferences to support and how users choose them |
| Translation success | A translation and its explanation must both be present; missing required content is a failure | Accuracy assessment and precise completeness criteria |
| Reply success | A suitable response | Required reply content and failure criteria |
| Rules | To be defined by the owner after discussing examples | Meaning preservation, explanation relevance, and reply-intent handling |
| Failures | Use different messages for different failure types | Failure categories, clarification behavior, and wording |

Current review focus: use the shared conversation to define what successful sentence feedback includes, then specify outputs for the other tasks. Formatting choices, proposed rules, evaluation criteria, and error behavior require further discussion. No domain model, use-case contract, or implementation is finalized by this review.

## 1. Goal and decisions

The two main flows help the user draft replies and learn their selected language from explanations in LINE. Japanese is the initial target language.

| Decision | Status |
| --- | --- |
| Main flows: Reply Bot and Tutorial Bot | Confirmed by the owner |
| Reply Bot drafts a suitable response in the target language | Japanese is the initial target |
| Tutorial Bot first-version tasks | Confirmed by the owner: translate and explain, check a draft, and answer a grammar question |
| All user interaction happens in LINE | Confirmed by the original request |
| Integrations: LINE Messaging API and OpenAI API | Confirmed by the original request |
| Implementation language: Python | Recommended following the latest discussion; replaces the initial Java direction |
| HTTP framework: FastAPI | Recommended following the latest discussion |
| Architecture: Clean Architecture | Confirmed by the original request |
| Project initialization and domain/use-case design | Owned by the user; confirmed in the latest discussion |
| Implementation | Owned by the assistant after reviewing the user's design |
| First version is for the owner's personal use | Confirmed in discussion |
| Access to the two flows | Proposed: select Reply Bot or Tutorial Bot in the same LINE chat, using the existing mode selection plan |
| Tutorial Bot task selection | Give feedback on standalone drafts in the target language by default. Accept natural language requests and ask only when the task is still unclear. |
| Sentence feedback | Correct and explain errors. When the draft is correct, check for a more natural phrasing and explain when it fits. |
| Language choices | Pass user-entered text through as typed. Use independent language tags for the language being learned (`target_language`, initially `ja`) and the language of explanations (`tutorial_language`, initially `zh-TW`). |
| Missing or unclear reply intent | Owner decision: ask what the user wants to communicate before drafting; draft directly when the intent is clear |
| Follow-up requests use recent-session context | Confirmed in discussion |
| Translation completeness | Owner-defined: both translation and learning explanation are required; missing required content is a failure |
| Exact explanation format and example outputs | Pending; user will provide examples |

Everything below marked “proposed” remains open to revision. The recommended stack is Python + FastAPI. Database, deployment platform, model, package tooling, and numerical limits have not been selected.

## 2. Proposed MVP boundary

The proposed first version supports one-on-one text conversations with the owner’s LINE account. Access is restricted using a configured LINE user ID.

The working assumption is one LINE chat with two selectable flows:

| Flow | User goal | Initial capability |
| --- | --- | --- |
| Reply Bot | Respond to a message they received | Draft a copyable reply in the target language based on their intended meaning |
| Tutorial Bot | Learn how to express something in the target language, improve a sentence, or understand grammar | Translate and explain, check a draft, or answer a grammar question |

Both flows use the existing mode selection, recent context, reset, and failure handling requirements.

Voice, images, public onboarding, group chats, saved vocabulary collections, quizzes, scheduled lessons, and a separate web interface are possible later extensions. They are not requirements for this draft.

The bot sees messages sent to its own chat. In Reply Bot, the user pastes the received sentence and any relevant context. It does not have access to unrelated personal LINE conversations. Suggested replies are returned to the user for copying.

## 3. LINE interaction

Proposed controls:

| Control | Behavior |
| --- | --- |
| Reply Bot | Select the reply flow and start a new task |
| Tutorial Bot | Select the tutorial flow to translate and explain, check a draft, or ask a grammar question |
| More polite / More casual | Revise the current answer |
| Explain more | Expand the current learning explanation when one exists |
| New task | Start a new task while keeping the selected flow |
| Reset | Clear recent learning context and show mode selection |

Use LINE quick-reply postback actions initially. Quick replies support postback actions; a permanent rich menu can be added if useful. [1]

The bot confirms the selected flow. Switching flows clears the previous task, so a message being studied in Tutorial Bot does not become a reply target.

A message received before mode selection prompts the user to select a mode and preserves the submitted text for that selection.

Inside Tutorial Bot, users write in ordinary language without choosing a task button. Resolve the requested task in this order:

1. Honor an explicit request or a clear follow-up in the current task. A grammar question can be written in the target language. A short follow-up such as “文法” after a sentence check asks for more detail about that sentence.
2. When the user submits a draft in the target language on its own, give sentence feedback directly. A question the user is practicing, such as “どれが食べたい？”, can be a draft too. Check correctness and naturalness after choosing this task.
3. If the message and context still do not establish what the user wants, ask one focused question. Keep the original text so the user can clarify without repeating it.

Natural follow-ups such as “make it shorter” should work within the current task. How the app recognizes the requested Tutorial Bot task remains open.

## 4. Reply Bot

Goal: turn what the user wants to communicate into a copyable reply in the target language.

Input:

- Required to start: the received sentence, initially proposed to be Japanese.
- Required before drafting: what the user wants to communicate, such as “accept,” “decline politely,” or “ask to reschedule.” The user can supply it with the sentence or answer a clarification.
- Optional: relevant preceding messages.
- Optional: recipient relationship and desired tone.

Proposed output:

- The meaning and relevant nuance of the received sentence.
- One recommended reply in the target language, or a small set of clearly labeled phrasings that express the same intent.
- The meaning of each reply and why its tone fits.
- Key grammar and vocabulary explanations for the suggested reply, using the same types of learning notes as Tutorial Bot.

The number of replies and inclusion of learning explanations are proposals the owner has yet to confirm.

Confirmed reply flow: if the user’s intent is missing or unclear, ask one focused question before offering a draft. For example, if they paste “明日の打ち合わせに参加できますか。”, ask whether they want to accept, decline, or suggest another time. Retain the received sentence in the current session so the user can answer without pasting it again. A clarification is an expected intermediate outcome of this flow.

When the user’s intent is clear, draft a reply directly and preserve that intent. Avoid requiring recipient and tone questions when an ordinary polite default is sufficient.

Open decision: what information should accompany the draft for a complete reply?

## 5. Tutorial Bot

Goal: help the user express ideas, improve sentences, and understand grammar in the target language.

The owner confirmed all three tasks below for the first version. The correction and grammar answer formats are proposals for the owner to review.

### Translate and explain

Owner-defined completion requirement: return both the translation and its vocabulary/grammar explanation. If required content is missing, the generation attempt is incomplete and must not be presented as a successful answer. Completeness checks and linguistic quality evaluation are separate; precise validation rules remain to be defined with the owner.

Input:

- Required: source sentence.
- Optional: setting, recipient relationship, desired tone, and intended nuance.
- Pass the source text to the evaluator as typed. The target language selects the language of the translation.

Output:

- A natural translation in the target language that preserves the intended meaning.
- The meaning in the explanation language.
- Key grammar explanations tied to expressions actually used in the translation.
- Important vocabulary, with meanings and readings where useful, such as kana for Japanese.
- Tone and usage notes when they affect whether the sentence is suitable.
- Alternatives only when they clarify a meaningful difference.

Quality rules:

- Do not add facts, commitments, or details absent from the source.
- Prefer natural phrasing over a mechanically literal translation.
- Explain conjugation and sentence construction when useful to the learner.
- State assumptions when context changes the translation materially.
- Ask a short question when an ambiguity prevents a useful translation.
- Keep the translated sentence easy to copy independently of its explanation.

### Check a sentence

Input includes a draft to check in the target language and optional context such as intended meaning, recipient, and desired tone. `CheckSentenceRequest` passes the draft, context, `target_language`, and `tutorial_language` to the evaluator.

| Assessment | Expected feedback |
| --- | --- |
| The draft needs a correction | Give a copyable corrected sentence and explain the specific grammar, form, or word choice that needs fixing. |
| The draft is correct but another phrasing fits the context better | Say the original is valid. Give the more natural version as a suggestion and explain what makes it a better fit, such as tone or word choice. |
| The draft is already correct and natural | Render exactly `Well done!`. |

Preserve the intended meaning and tone. When a more casual or polite alternative is useful, label it separately so a change in register is clear. If the likely meaning is clear enough, give feedback directly. Ask what the user meant only when the ambiguity would materially change the correction.

Style reference: [日本語の会話](https://chatgpt.com/share/6af9734e-2be0-83ee-84c2-fc9f4bcb2761), supplied by the owner. Use it as a reference for leading with a usable Japanese sentence, explaining the reason in Traditional Chinese, and adding a reading, conjugation, or brief contrast when it helps. Keep readings separate from the copyable sentence. Exact formatting and explanation length remain open.

Examples adapted from the reference:

| Input and context | What the bot should do |
| --- | --- |
| `買い見ます`, when the user means “I'll try buying it” | Correct to `買ってみます` and explain that “try doing” uses the verb’s て-form followed by `みる`. |
| `はい、行こう`, in casual chat with a friend | Confirm that it is grammatically valid. Suggest `うん、行こう` and explain that `うん` matches the casual tone of `行こう`. |
| `今度、ぜひ食べてみるよ`, in casual chat | Render `Well done!`. |
| `まずくて vs まずかったから` after discussing a sentence about apples | Compare the two forms as a grammar follow-up. Explain the distinction in context. |

### Answer a grammar question

- Input includes a question about the target language’s grammar. The user may supply an example sentence or refer to one in the current task.
- Proposed result: answer the question directly, then explain how the form is built and when to use it, as relevant. Include a short example in the target language with its meaning. When the question compares two forms, explain when each fits.
- Proposed rule: if the answer depends on a sentence the bot does not have, ask for that sentence before explaining its specific usage.

The target language and tutorial language are independent application inputs with open language tags. For example, a request can set `target_language="fr"` to check a French draft and `tutorial_language="en"` to get an English explanation. The exact detail level, ordering, readings, examples, comparisons, and common-mistake notes will be defined from the user’s sample output.

## 6. Recent-session behavior

Confirmed: recent-session context is required.

Proposed implementation rules:

- Store the active task, relevant user inputs, selected reply intent, and the latest successful result.
- Store an explicit pending clarification with the input it refers to so the user's answer can resume the task.
- Start with at most six recent user/bot exchanges and a 30-minute inactivity expiry, also bounded by a configured token budget.
- Keep the selected mode separately from expiring task content.
- A new task clears unrelated context.
- Reset clears the active task and pending clarification.
- After context expires, a follow-up asks the user to resend the relevant sentence or question.
- A follow-up to a failed request cannot silently modify an older successful result.
- Expired content is excluded from prompts immediately and removed by cleanup.
- An unsent message is removed from retained context and pending work when its LINE unsend event is received; already transmitted provider requests cannot be retracted. [2]

The turn count, expiry, retention, and behavior across application restarts remain proposed. No long-term learning history is required.

## 7. Python, FastAPI, and Clean Architecture

Recommended runtime: a single Python application with FastAPI for the HTTP boundary. FastAPI provides request validation and dependency injection; the domain and application use cases remain independent of it. [3]

Selection rationale: the current scope is a personal chatbot with two user-facing flows. Python matches the owner's existing FastAPI experience and provides a direct path to AI experimentation. This should reduce initial implementation overhead and leave more time for prompt evaluation and learning-content quality. This is a project-specific assessment; Java could also meet the requirements. Java practice is now a separate project goal.

| Layer | Responsibilities | Examples |
| --- | --- | --- |
| Domain | Learning concepts and rules | LearningMode, ReplyTone, LearningPreferences, session state rules |
| Application | Use cases and provider-independent contracts | CheckSentence, TranslateSentence, SuggestReply, RefineAnswer, ChangeMode, ResetSession |
| Presentation | Receive LINE events and render user-facing messages | Webhook controller, event-to-request mapping, LINE response renderer |
| Infrastructure | Implement external integrations and storage | OpenAI adapter, LINE delivery adapter, persistence adapters |
| Composition root | Wire dependencies and configuration | Application startup and dependency wiring |

Dependency rule: domain has no framework or provider dependencies. Application depends on domain and defines the interfaces it needs. Presentation and infrastructure depend inward; application does not import either.

Proposed application-owned ports:

- LanguageLearningPort: translate, suggest replies, and refine an answer.
- SessionRepository: load and update recent task context.
- WorkItemRepository: durably accept, deduplicate, and claim incoming work.
- MessageDeliveryPort: deliver a result through a channel-neutral contract.

Provider request/response objects remain inside adapters. LINE-specific rendering belongs at the outer boundary. Application result contracts remain ordinary Python types, using dataclasses where helpful. Use enums and dataclasses for domain concepts; use Protocols or abstract interfaces for application-owned ports. Pydantic schemas validate external requests and model output at the presentation and infrastructure boundaries, then map into application contracts.

Use Python type annotations and static checking in CI for internal contracts. Runtime validation remains necessary for external payloads and does not establish the linguistic accuracy of generated content.

Suggested package names: domain, application, presentation.line, infrastructure.openai, infrastructure.line, infrastructure.persistence, and bootstrap. Keep the framework composition and SDK imports outside domain and application.

Database choice remains open. A relational database could store short sessions and a durable work queue without introducing an external broker. That is a proposed implementation option, not a requirement to use PostgreSQL or microservices.

## 8. OpenAI integration and output contracts

Proposed API: Responses API, which OpenAI recommends for new projects. Use Structured Outputs with a supported model to obtain schema-constrained results, then map them into Python application contracts. [4][5]

Proposed: version prompts by operation, covering Reply Bot drafting, each Tutorial Bot task, and refinement. User-provided sentences and quoted conversation are input data, not instructions that can change the task or output contract.

The local `SentenceEvaluation` contract returns `kind`, copyable `sentence` in the target language for a correction or suggestion, and `explanation` in the tutorial language. Suggestions also require an `original_validity_note` in the tutorial language. The remaining result fields are proposals.

| Contract | Main fields |
| --- | --- |
| TranslationResult | translatedText, meaning, grammarPoints, vocabularyItems, usageNotes, alternatives |
| ReplyAssistanceResult | receivedMeaning, replyOptions, grammarPoints, vocabularyItems |
| ReplyOption | replyText, meaning, tone, intendedStance, suitabilityNote |
| GrammarPoint | expression, construction, meaning, usageExplanation |
| VocabularyItem | term, reading, meaning, usageNote |
| ClarificationNeeded | question, optional choices |

Prompt configuration and the provider schema must match these application contracts. Metadata such as request ID, task ID, schema version, model, and prompt version is assigned or recorded by the backend.

Validate required fields and bounded lengths before rendering. Handle provider refusal, incomplete generation, timeout, and schema failure as explicit outcomes. Schema adherence does not establish linguistic correctness; language quality requires evaluation.

The backend controls message formatting. OpenAI produces learning content rather than complete LINE payloads.

Start with the official Python OpenAI SDK for direct API calls. [8] The initial workflow does not require an agent orchestration framework. Revisit that choice when a feature requires model-selected tools or a multi-step agent loop.

Model selection is deferred until representative examples can be evaluated for quality in the target language, explanation accuracy, latency, and cost. The spec does not require a specific model, agent framework, RAG system, or tool-calling workflow.

## 9. Webhook processing and delivery

Proposed flow:

1. Verify LINE’s signature against the unchanged raw request body before processing events. [6]
2. Parse supported events and check the owner allowlist.
3. Deduplicate each event using webhookEventId and durably save accepted work.
4. Return HTTP 200 promptly after successful acceptance; return a retryable failure if durable acceptance fails.
5. A background worker loads session context and invokes the relevant use case.
6. Save the validated result, render bounded LINE messages, and deliver through LINE.
7. Record delivery status separately from generation status.

A valid empty verification event receives HTTP 200 without generating a learning answer. Unsupported content receives a brief text-input instruction when appropriate.

LINE recommends asynchronous event processing. Duplicate events and redelivery can occur; redelivery may change event ordering. [2] Claim work atomically, process one active task operation per conversation, and prevent duplicate events from triggering another generation. A reset or mode change invalidates stale in-flight results.

LINE reply tokens are single-use and should be used immediately; use beyond one minute is not guaranteed. A reply request accepts at most five message objects. [7] Do not consume the token for a progress message and assume it remains available for the answer.

Proposed initial deadline: aim to complete and reply within 20 seconds after webhook receipt. This is an application budget, not a provider guarantee. Bound model calls and retries accordingly.

If delivery has not occurred before the deadline, return a short retry instruction when the token remains usable. Do not automatically send a late answer afterward. If the token is already unusable, retain a failure status and let the next user interaction offer retry.

Push-message fallback is an open decision because it changes delivery behavior and quota requirements. Ambiguous delivery failures must not trigger a blind resend or a switch to push. Generation caching and delivery-state tracking reduce duplication, but the system does not claim exactly-once delivery across external API failures.

## 10. Operational requirements

Proposed minimums:

- Credentials come from environment configuration or managed secrets; they are not hard-coded or logged.
- Only the owner’s allowed LINE account can trigger paid generation.
- Configure input limits, output token limits, bounded retries, and a usage budget.
- Record request/task IDs, model and prompt versions, latency, token usage, and delivery status.
- Avoid logging raw learning conversations by default.
- Retain only the context needed for the recent-session feature.
- Distinguish session reset from any future permanent-history deletion.
- Choose OpenAI storage settings explicitly after reviewing its current data controls; resetting local session context is not a provider deletion operation.
- Provide a clear retry path for API outages or exhausted budgets.
- Maintain health checks and deploy behind a public HTTPS webhook endpoint.

Hosting, Python/FastAPI versions, package tooling, database, request limits, budget, and latency targets will be selected before implementation.

## 11. Acceptance criteria

| Scenario | Expected behavior |
| --- | --- |
| User selects Reply Bot and supplies a received sentence and desired stance | Returns a suitable reply in the target language that preserves that stance |
| User requests a translation in Tutorial Bot | Returns a translation in the target language plus grammar and vocabulary explanations |
| User enters a draft in the target language with an error and no explicit task | Corrects the draft and explains the error without asking which tutorial task to perform |
| User enters a grammatically valid draft that could sound more natural in context | Confirms the original is valid, offers an optional phrasing, and explains what makes it a better fit |
| User enters a draft that is already natural | Renders exactly `Well done!` |
| User asks a grammar question in the target language or clearly refers to the previous sentence’s grammar | Answers the grammar question directly |
| User asks Tutorial Bot a standalone grammar question | Proposed: answers the question directly with a usage explanation and an example in the target language |
| User clearly requests a tutorial task in ordinary language | Proceeds with the task without asking the user to choose or confirm it |
| User sends ambiguous text in Tutorial Bot and context does not resolve the task | Asks a focused question about what the user wants to do |
| User clarifies a tutorial request in the same session | Performs the selected task using the original text and the clarification |
| The user submits a received sentence with missing or unclear reply intent | Asks one focused question and waits before drafting |
| The user answers the Reply Bot clarification in the same session | Drafts the reply using the original received sentence and the newly stated intent |
| User asks “make it more polite” in the same session | Revises the current task’s answer without resending its sentence |
| User switches flows or starts a new task | Previous task context, including any pending clarification, does not affect the new answer |
| User resets during generation | The superseded result is not delivered later |
| Session expires | Follow-up requests ask for the relevant sentence or question again |
| LINE repeats the same webhook | Does not perform a second generation for that event |
| Webhook has an invalid signature | Does not process its contents |
| Model output is incomplete, refused, or invalid | Returns a controlled failure or retry instruction; never exposes raw provider output |
| Generated content exceeds a delivery limit | Renders within limits or offers continuation; does not send a rejected payload |

Verification plan: use-case tests with fake ports; webhook signature and deduplication tests; adapter contract tests; manual LINE end-to-end checks; and a language evaluation set based on the user’s examples. Review meaning preservation, naturalness, tone, grammar accuracy, vocabulary readings, and explanation usefulness. Accept multiple valid phrasings when evaluating language quality.

## 12. Decisions for the next discussion

1. Tutorial Bot output: review the sentence feedback examples, settle the minimum answer format, and specify the translation and grammar question examples.
2. Reply Bot completeness: which explanation, if any, should accompany each draft?
3. Tutorial Bot explanation detail and per-language quality examples; `zh-TW` is the initial default and the contract remains open to additional language tags.
4. Reply styles: casual, polite, business, or a smaller initial set?
5. Target languages to evaluate after Japanese.
6. Session expiry, number of retained turns, and persistence across restarts.
7. Database, hosting, model, cost budget, package tooling, and push fallback.

Follow the mentored learning sequence in section 0. The owner will define the learning experience and behavior, then derive the domain and use cases. The examples elsewhere in this draft remain reference proposals until the owner adopts or revises them.

## Sources

Original API documentation reviewed on 2026-10-03; FastAPI and SDK documentation reviewed for the stack revision on 2026-10-04. Recheck API details before implementation.

1. [LINE: Use quick replies](https://developers.line.biz/en/docs/messaging-api/using-quick-reply/)
2. [LINE: Receive messages and webhook handling](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)
3. [FastAPI features](https://fastapi.tiangolo.com/features/)
4. [OpenAI: Responses API guidance](https://developers.openai.com/api/docs/guides/migrate-to-responses)
5. [OpenAI: Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
6. [LINE: Verify webhook signature](https://developers.line.biz/en/docs/messaging-api/verify-webhook-signature/)
7. [LINE: Messaging API reference](https://developers.line.biz/en/reference/messaging-api/nojs/)
8. [OpenAI: Official SDKs](https://developers.openai.com/api/docs/libraries)
9. [OpenAI: Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
