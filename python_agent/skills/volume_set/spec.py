from python_agent.skills.spec import ArgSpec, SkillSpec
from python_agent.skills.volume_set.examples import EXAMPLES
from python_agent.skills.volume_set.extractor import VolumeSetExtractor


SPEC = SkillSpec(
    name="volume_set",
    description="Set or change system volume",
    risk="low",
    extractor=VolumeSetExtractor(),
    args=[
        ArgSpec(
            name="mode",
            type="enum",
            required=True,
            values=["set", "delta"],
            description="Volume command mode",
        ),
        ArgSpec(
            name="percent",
            type="int",
            required=False,
            min_value=0,
            max_value=100,
            required_if={"mode": "set"},
            description="Target volume percent for mode=set",
        ),
        ArgSpec(
            name="delta",
            type="int",
            required=False,
            min_value=-100,
            max_value=100,
            required_if={"mode": "delta"},
            description="Volume delta for mode=delta",
        ),
    ],
    examples=EXAMPLES,
)
