# Research leadership and a separate PR-queue coordinator

Read this reference when several writers feed a shared landing queue. Use a separate queue coordinator when release timing, branch freshness and CI costs require sustained attention while research or implementation continues. A small queue may use one agent in both roles, but the ownership and authorization boundaries still apply. Do not create an extra standalone task without the user's request.

## Divide decisions, not just files

| Role | Owns | Supplies to the other role |
|---|---|---|
| Research or implementation lead | Priorities, evidence, acceptance criteria, specialist assignments and product progress | Exact candidate commit, intended behavior, evidence, dependencies, limitations and release holds |
| PR-queue coordinator | Queue inventory, integration worktree, landing order, batch membership, branch freshness, local gate receipts and authorized CI/merge timing | Integration conflicts, changed dependencies, tested commit, actual landed content and separately verified deployment state |

The work lead reads intervening repository changes to decide what remains useful. The queue coordinator audits whether those changes can land safely. Share that reconciliation rather than having both agents update the same branch. Neither role substitutes its judgment for an owner-only product decision, lifts a merge hold, or grants itself deployment permission.

Keep one writer per branch/worktree and one coordinator for readiness changes. Before queue integration, agree which exact head is being handed over and ask its writer to stop pushing to that branch. The writer can continue independent work elsewhere. Any necessary head change invalidates the old test/review claim and must be coordinated. A task ID, branch name or agent role alone is not a lock.

## How the research lead runs independent lanes

The research lead owns the programme's direction and synthesis; specialists own bounded questions and their assigned implementation. The lead may also own one difficult integration task, provided it does not become a bottleneck for every lane. A separate queue coordinator owns landing mechanics. Neither coordinator needs to redo each specialist's exploration.

### Begin with goals and a fresh reconciliation

Keep the owner's original goals, acceptance criteria and unfinished lanes in one durable progress record. At takeover, inspect relevant merged work, all open PRs that could affect the programme (including shared inputs), issues and outstanding local work; distinguish an already solved problem from a changed dependency or an unverified claim. The lead's audit asks what to investigate next; the queue coordinator's audit asks what can land. Share results and use one writer for the progress record.

Maintain a lane map with the owner/task ID, question, source/code/data versions, allowed files, dependencies, latest evidence, unresolved limit and next action. A lane can be researched, demonstrated locally, owner-confirmed, integrated or live; these are different claims. A side discovery should link back to the goal it serves, not displace harder unfinished goals.

### Dispatch bounded experiments, not open-ended optimism

- Give each specialist a concrete hypothesis or failure to investigate, pinned inputs, comparison baseline, measurable success criterion, resource/time limit and expected artifacts. Include relevant prior negatives so it does not repeat completed experiments unknowingly.
- Parallelize questions that can progress on independent inputs/files. If two lanes need the same interface or measurement contract, agree and version that contract first, or use separate adapters and serialize integration. Do not let several workers rewrite a central caller concurrently.
- Require an explicit return: finding in plain English, exact artifacts/code, input population and versions, commands and terminal outcome, resources consumed, limitations, and recommended next step. “Could work” is a proposal; a running process is not a result; an incomplete bounded search is not proof no solution exists.
- Reuse existing tasks when they remain available and appropriately scoped. On resumption inspect saved state before restarting a job. Consult the previous coordinator for focused historical questions, but verify recalled claims against durable evidence and current code.

### Integrate evidence before promoting a change

Inspect supporting outputs and material code changes rather than accepting a specialist summary alone. Use independent review when it addresses a meaningful uncertainty; do not multiply reviewers or rerun completed checks as a ritual. Keep failed experiments and counterexamples available, since they constrain the next hypothesis.

For empirical work, keep exploratory/tuning results separate from held-out evaluation. Record label revisions and exact candidate identity; repeated tuning on familiar examples does not create new independent evidence. A local feature preference, a whole-output grade, a model benchmark and production benefit are distinct outcomes. When the owner must judge alternatives, provide genuinely different, exactly bound candidates and use blind presentation when that is the agreed evaluation method.

The lead selects the next useful experiment based on evidence and dependencies, or prepares a reviewable implementation when a gain is established. Hand that implementation to the queue coordinator with its acceptance scope and remaining limitations. A promising score does not automatically authorize a gate or product change. Deployment receipts flow back from the queue coordinator into the progress record; they do not replace scientific acceptance.

### Keep continuity without duplicate management

Workers write their evidence in owned locations and message the lead at a meaningful result, blocker or interface change. The lead updates the shared progress record; the queue coordinator updates the queue state. Use exact task IDs, artifact paths and commit IDs in cross-session requests. Avoid frequent unchanged polling and broad messages that wake every lane unnecessarily.

At a resource stop or handoff, record actual process state, completed versus pending work, failed attempts, cost, exact continuation commands and ownership. Preserve artifacts outside temporary-only storage. Resume from that checkpoint after current-state reconciliation; a handoff is not completion of the research goal.

## The handoff between lanes

Use the existing project queue record; avoid creating a competing tracker. For each candidate record:

- PR, current head/base SHA, branch, owning task and worktree; intended artifact or behavior to verify after landing.
- Dependencies, shared files and indirect shared inputs; whether another PR or current main already contains the work.
- Exact local checks, test counts, terminal exits and logs, with the commit they tested; unresolved failures and review findings.
- Runtime/deployment classification, explicit holds and the scope/source of any applicable release authorization.
- Next action and responsible session. Distinguish draft, locally verified, ready, merged, content delivered via a batch, and verified live.

An agent's “ready” report is evidence to inspect. It is not permission to flip a draft. Queue coordination does not turn research measurements or owner feature preferences into a production setting.

## Follow the repository's landing procedure

Read current repository instructions, batch/CI runbooks and the landing helper's read-only mode before invoking it. Prefer its documented procedure over a parallel home-grown queue tool. If a named runbook is absent from a stale checkout, locate it in an appropriate current checkout/ref; do not infer it does not exist. Do not edit another session's worktree to obtain it.

Re-check current heads and the candidate's premise before selecting a batch. File overlap is only the first check: a test sweeping a directory, a shared census, a generated page or a loader can make disjoint diffs interact. Remove held or obsolete members. Use the repository's history strategy, declaration requirements and full combined-tree gate policy.

Do not change a head while a useful check on that head is running. If a run demonstrably cannot lead to a merge, follow the authorized cancellation/recovery procedure; record why, then update and revalidate. Do not repeatedly cancel/restart in pursuit of a moving main. Defer other branches until their landing slot.

After landing, verify the delivered artifact/content against the pinned tested tree. Squash and batch merges make ancestry alone unreliable; an original member PR can remain unmerged while its content is delivered. Use the actual landed commit, not a speculative merge-preview SHA. Report deployment separately. Preserve ignored artifacts and otherwise unreferenced commits before removing any worktree.

## Lessons to apply during integration

1. **Stale generated data needs re-derivation.** A clean conflict resolution does not refresh renamed fields, changed populations or source records. Find downstream readers before changing a shared input. Rebuild and validate against the new sources, not by adjusting expected numbers to match.
2. **A guard's subject can change while its assertion keeps passing.** For a claim about a named subject, look it up by stable name/ID and raise when it is missing or ambiguous. Do not use “largest,” “best,” “first match” or another ranking as a substitute for identity. Synthetic example: a report about the `checkout` service selects whichever service has the most requests. When `search` becomes busier, its assertions still pass but the figures are mislabeled as `checkout`. A nonempty result and a true numeric assertion do not protect the subject. Bind the report and guard to the same named source identity. Where applicable, verify that identity's source version too. A useful regression adds a larger unrelated candidate and proves the named subject stays selected; removing the named subject must fail, not fall back. Ranking is appropriate when the question actually asks for the largest item, but the output must then identify whichever item was selected rather than retain a fixed service's label.
3. **A claimed pre-existing failure needs a control.** Run the failing check on an isolated clean current target using the same environment before attributing it to main. Record both outcomes; an unavailable control is not a clean control.
4. **Structured conflicts need structured comparison.** Compare base, member and target by row ID and complete row body. Parse reconstructed rows, verify expected additions/edits/removals and duplicate IDs, and check that resolutions did not invent rewordings. Counts and balanced braces alone cannot establish correctness.
5. **A green wrapper can hide failed or empty tests.** Use the CI-compatible environment and capture the test process's exit directly, not a trailing log-filter command's status. Check collection and completion. Separate suites with colliding import namespaces. Serialize tests that mutate shared fixtures and check that real files survived.
6. **A narrow impact check is not deployment classification.** A check covering output sizes can miss changes to acceptance behavior. Read what the check actually executes; classify the complete runtime diff and verify the deployed result using the repository's mechanism.
7. **Preserve reviewable checkpoints.** When pushing is authorized, commit explicit paths and checkpoint coherent draft work after the required local checks. Coordinate with queue ownership and active CI; frequent checkpoints are not permission to push every intermediate edit or interrupt a landing run.

## Adapt the landing safeguards to the target repository

Read the current batch-landing, CI-cost, deployment and repository instruction documents before acting. Discover their actual paths and helper commands; this reference does not prescribe a particular project's scripts, schemas, cloud provider or queue. Resolve conflicting historical notes using current instructions and applicable owner decisions.

- Use the project's CI-compatible runtime and required local checks before an authorized push. Isolate test suites with conflicting import namespaces and execute all required language-specific checks. Do not hardcode historical suite counts, interpreter versions or CI prices.
- Where the project supports batching, group independent ready changes to reduce repeated validation and base updates. Account for shared metadata conflicts and indirect dependencies. Use a separate integration worktree, the project's required history strategy and its full combined-tree validation policy. Disable automatic stashing where it would interfere with other worktrees.
- Keep drafts until their authorized landing slot. Carry each member's required change declarations into the batch review. If drafts have cheaper preliminary checks, clear those before triggering the full pipeline. Where each merge makes other branches ineligible, serialize ready changes and refresh only the next candidate; do not impose that rule on a repository with a managed merge queue that provides different guarantees.
- Use a landing helper's documented read-only or dry-run mode for inspection. A command that appears to inspect a draft may also mark it ready or start paid CI. Verify its behavior, queue order and active holds before execution. Let the repository's mechanism register new checks before enabling automatic merge where that ordering is required.
- Stage explicit paths, work in an owned checkout, and avoid shared stash operations. Do not write into another session's worktree or replace a useful in-flight head.
- Some tests temporarily rewrite real project files. Serialize them with other readers/writers of those files and compare the resulting bytes with the intended pre-test state. Report mismatches rather than silently restoring. Validate structured merge results after each member, with explicit comparison refs.
- Classify the complete runtime diff and check whether merging can deploy automatically. Use the project's authorized verifier to record deployment state; do not invent a live revision or manually edit generated deployment metadata. Keep deployment receipts distinct from research source-provenance records. Updating a source stamp must not make an unverified old conclusion appear freshly validated.

Keep current PR numbers, hold decisions, service revisions, costs, internal paths and product priorities in private project records. Preserve a hold until validly released. Send new product targets to the work lead rather than treating them as permission to expand queue work.
