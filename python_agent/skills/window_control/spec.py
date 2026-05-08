from python_agent.skills.spec import ArgSpec, SkillSpec
from python_agent.skills.window_control.examples import EXAMPLES
from python_agent.skills.window_control.extractor import WindowControlExtractor


SPEC = SkillSpec(
    name="window_control",
    description="Close, minimize, maximize, or restore a window",
    risk="medium",
    extractor=WindowControlExtractor(),
    args=[
        ArgSpec(
            name="action",
            type="enum",
            required=True,
            values=["close", "minimize", "maximize", "restore"],
        ),
        ArgSpec(name="target_type", type="enum", required=True, values=["app", "current"]),
        ArgSpec(name="app_id", type="string", required=False),
    ],
    examples=EXAMPLES,
)
