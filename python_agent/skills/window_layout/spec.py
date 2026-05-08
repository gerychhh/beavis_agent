from python_agent.skills.spec import ArgSpec, SkillSpec
from python_agent.skills.window_layout.examples import EXAMPLES
from python_agent.skills.window_layout.extractor import WindowLayoutExtractor


SPEC = SkillSpec(
    name="window_layout",
    description="Move or arrange one or more windows",
    risk="medium",
    extractor=WindowLayoutExtractor(),
    args=[
        ArgSpec(name="layout", type="string", required=True),
        ArgSpec(name="targets", type="list", required=True),
    ],
    examples=EXAMPLES,
)
