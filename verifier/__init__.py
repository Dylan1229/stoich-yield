"""The deterministic verifier: each tool's checks live in its own module, on contract instances."""

from contract import Task, Tool

from . import balance, parse, pin, task, worksheet

TOOLS = {
    Tool.PARSE_FORMULA: parse,
    Tool.CHECK_BALANCE: balance,
    Tool.SAVE_WORKSHEET: worksheet,
    Tool.PIN_YIELD: pin,
}


def _tool_output(module):
    """A tool task's check: its output judged as its one tool's verify_output judges it."""
    return lambda arguments, output, reference, workspace: module.verify_output(arguments, output, workspace)


# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {
    Task.PARSE_FORMULA: _tool_output(parse),
    Task.BALANCE_AND_YIELD: task.verify_task,
}


def verify_input(tool, value):
    return TOOLS[Tool(tool)].verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
