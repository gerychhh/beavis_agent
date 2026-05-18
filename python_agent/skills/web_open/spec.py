from python_agent.skills.spec import ArgSpec, SkillSpec
from python_agent.skills.web_open.examples import EXAMPLES
from python_agent.skills.web_open.extractor import WebOpenExtractor


SPEC = SkillSpec(
    name="web_open",
    description="Open a web site or direct URL in the default browser",
    risk="low",
    extractor=WebOpenExtractor(),
    args=[
        ArgSpec(name="action", type="enum", required=True, values=["open"]),
        ArgSpec(name="site_id", type="string", required=False),
        ArgSpec(name="url", type="string", required=True),
    ],
    examples=EXAMPLES,
)
