# Extract of claude-prompting-best-practices.md

Title: Prompting best practices
Source URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
Fetch time: 2026-10-13T09:10:16Z
Full snapshot: 68042 bytes, sha256 057fbadeb4e83266404886593a727fc375ee22bc172126040fc7e7a239f21acf
Extract size: 8482 of 68042 bytes (12.5%)

Full text not committed (licence/size); re-fetch from the URL and verify the sha256.
Entries below are the quotes cited by the checklist, each with the line number and section heading in the full snapshot at the hash above. Quote presence in the full snapshot was verified when the checklist was built (see .scratch only); this folder lets a reader re-fetch the source and confirm each quote and location.
Line numbers refer to the full snapshot (as converted text).

-----
L34 | General principles | "Where a technique names a specific model, treat it as measured on that model and re-check it against your own evals before applying it to another."
L38 | Be clear and direct | "If you want "above and beyond" behavior, explicitly request it rather than relying on the model to infer this from vague prompts."
L42 | Be clear and direct | "Show your prompt to a colleague with minimal context on the task and ask them to follow it. If they'd be confused, Claude will be too."
L63 | Add context to improve performance | "Providing context or motivation behind your instructions, such as explaining to Claude why such behavior is important, can help Claude better understand your goals and deliver more targeted responses."
L79 | Add context to improve performance | "Claude is smart enough to generalize from the explanation."
L92 | Use examples effectively | "Include 3–5 examples for best results."
L97 | Structure prompts with XML tags | "XML tags help Claude parse complex prompts unambiguously, especially when your prompt mixes instructions, context, examples, and variable inputs."
L106 | Give Claude a role | "Setting a role in the system prompt focuses Claude's behavior and tone for your use case."
L246 | Long context prompting | "Place your long documents and inputs near the top of your prompt, above your query, instructions, and examples."
L329 | Communication style and verbosity | "May skip detailed summaries for efficiency unless prompted otherwise"
L334 | Communication style and verbosity | "After completing a task that involves tool use, provide a quick summary of the work you've done."
L337 | Communication style and verbosity | "its default user-facing responses run longer than prior models'"
L337 | Communication style and verbosity | "Ask for progress text explicitly, and remove any instruction telling it to keep that text brief."
L343 | Control the format of responses | "Tell Claude what to do instead of what not to do"
L354 | Control the format of responses | "removing markdown from your prompt can reduce the volume of markdown in the output."
L382 | Control the format of responses | "Claude Fable 5.1 already formats less than earlier models, so on that model a block like this can suppress structure the content needs."
L445 | Tool usage | "Claude's latest models are trained for precise instruction following and benefit from explicit direction to use specific tools."
L445 | Tool usage | "Claude will sometimes provide suggestions rather than implementing them, even if making changes might be what you intended."
L473 | Tool usage | "By default, implement changes rather than only suggesting them."
L485 | Tool usage | "default to providing information, doing research, and providing recommendations rather than taking action"
L491 | Tool usage | "If your prompts were designed to reduce undertriggering on tools or skills, these models may now overtrigger. The fix is to dial back any aggressive language."
L501 | Optimize parallel tool calling | "While the model has a high success rate in parallel tool calling without prompting"
L521 | Optimize parallel tool calling | "On Claude Fable 5.1 in long agent loops, send the parallel-calls instruction as a turn-scoped system message after each round of tool results."
L529 | Overthinking and excessive thoroughness | "Replace blanket defaults with more targeted instructions."
L530 | Overthinking and excessive thoroughness | "Instructions like "If in doubt, use \[tool]" will cause overtriggering."
L531 | Overthinking and excessive thoroughness | "If Claude continues to be overly aggressive, use a lower setting for `effort`."
L548 | Leverage thinking & interleaved thinking capabilities | "On Claude Fable 5.1, Claude Mythos 5.1, Claude Fable 5, Claude Mythos 5, and Claude Opus 5.5, thinking is always on and adaptive thinking is the only mode."
L560 | Leverage thinking & interleaved thinking capabilities | "If you find the model thinking more often than you'd like, which can happen with large or complex system prompts, add guidance to steer it:"
L777 | Leverage thinking & interleaved thinking capabilities | "On Claude Sonnet 5.5, the lowest thinking setting is `between_tools`, accepted at effort `high` or lower."
L779 | Leverage thinking & interleaved thinking capabilities | "A prompt like "think thoroughly" often produces better reasoning than a hand-written step-by-step plan."
L781 | Leverage thinking & interleaved thinking capabilities | "a prompt that asks the model to write out its reasoning, for example in `<thinking>` tags, may be declined."
L782 | Leverage thinking & interleaved thinking capabilities | "Append something like "Before you finish, verify your answer against \[test criteria]."
L782 | Leverage thinking & interleaved thinking capabilities | "verification instructions carried over from prompts tuned for earlier models can cause over-verification, adding tokens and latency."
L785 | Leverage thinking & interleaved thinking capabilities | "Claude Opus 4.5 is particularly sensitive to the word "think" and its variants."
L804 | Context awareness and multiwindow workflows | "If you are using Claude in an agent harness that compacts context or allows saving context to external files (like in Claude Code), consider adding this information to your prompt"
L824 | Workflows across multiple context windows | "It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality."
L828 | Workflows across multiple context windows | "When a context window is cleared, consider starting with a brand new context window rather than using compaction."
L834 | Workflows across multiple context windows | "As the length of autonomous tasks grows, Claude needs to verify correctness without continuous human feedback."
L849 | State management best practices | "Git provides a log of what's been done and checkpoints that can be restored."
L879 | Balancing autonomy and safety | "Without guidance, Claude Opus 4.6 may take actions that are difficult to reverse or affect shared systems"
L920 | Subagent orchestration | "These models can recognize when tasks would benefit from delegating work to specialized subagents and do so proactively without requiring explicit instruction."
L926 | Subagent orchestration | "Claude Opus 5 also delegates to subagents more readily than prior models"
L932 | Subagent orchestration | "For simple tasks, sequential operations, single-file edits, or tasks where you need to maintain context across steps, work directly rather than delegating."
L950 | Reduce file creation in agentic coding | "If you create any temporary new files, scripts, or helper files for iteration, clean up these files by removing them at the end of the task."
L956 | Overeagerness | "Claude Opus 4.5 and Claude Opus 4.6 have a tendency to overengineer by creating extra files, adding unnecessary abstractions, or building in flexibility that wasn't requested."
L976 | Overeagerness | "The right amount of complexity is the minimum needed for the current task."
L982 | Avoid focusing on passing tests and hardcoding | "Claude can sometimes focus too heavily on making tests pass at the expense of more general solutions"
L1006 | Minimizing hallucinations in agentic coding | "Never speculate about code you have not opened."
L1076 | Migration considerations | "Adding modifiers that encourage Claude to increase the quality and detail of its output can help better shape Claude's performance."
L1084 | Migration considerations | "Claude 4.6 models are more proactive and may overtrigger on instructions that were needed for previous models."
