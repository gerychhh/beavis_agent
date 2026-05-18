from python_agent.skills.spec import ArgSpec, SkillSpec
from python_agent.skills.web_search.examples import EXAMPLES
from python_agent.skills.web_search.extractor import WebSearchExtractor


SPEC = SkillSpec(
    name="web_search",
    description="Search the web with Google in the default browser",
    risk="low",
    extractor=WebSearchExtractor(),
    args=[
        ArgSpec(name="action", type="enum", required=True, values=["search"]),
        ArgSpec(name="provider", type="enum", required=True, values=["google"]),
        ArgSpec(name="query", type="string", required=True),
        ArgSpec(name="url", type="string", required=True),
    ],
    examples=EXAMPLES,
)
