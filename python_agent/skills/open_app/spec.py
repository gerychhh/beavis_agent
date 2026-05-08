from python_agent.skills.open_app.examples import EXAMPLES
from python_agent.skills.open_app.extractor import OpenAppExtractor
from python_agent.skills.spec import ArgSpec, SkillSpec


SPEC = SkillSpec(
    name="open_app",
    description="Open or focus a Windows application",
    risk="low",
    extractor=OpenAppExtractor(),
    args=[
        ArgSpec(name="app_id", type="string", required=True),
    ],
    examples=EXAMPLES,
)
