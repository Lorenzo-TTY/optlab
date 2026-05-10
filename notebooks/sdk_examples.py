"""Notebook-friendly SDK examples for OptLab.

Run after installing the backend package in editable mode:

    cd D:\mltest\backend
    pip install -e ".[dev]"
    python ..\notebooks\sdk_examples.py
"""

from pathlib import Path

from optlab.sdk import run_builtin_zdt1, run_http_problem, run_python_plugin_problem


if __name__ == "__main__":
    print(run_builtin_zdt1(max_evals=16).summary)
    print("Python plugin example:")
    print(
        "run_python_plugin_problem(",
        Path("my_plugin.py"),
        "function_name='evaluate', max_evals=32)",
    )
    print("HTTP example:")
    print("run_http_problem('http://127.0.0.1:8000/evaluate', max_evals=32)")


# Example plugin file shape:
#
# def evaluate(variables):
#     return {
#         "objectives": {"f1": variables["x1"], "f2": 1.0 - variables["x2"]},
#         "constraints": {},
#         "metadata": {"source": "notebook-plugin"},
#     }
