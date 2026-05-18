#include <iostream>
#include <iterator>
#include <memory>
#include <string>

#include <nlohmann/json.hpp>

#include "core/SkillResult.h"
#include "executor/Executor.h"
#include "executor/SkillRegistry.h"
#include "skills/apps/OpenAppSkill.h"
#include "skills/system/VolumeSetSkill.h"
#include "skills/web/WebOpenSkill.h"
#include "skills/web/WebSearchSkill.h"
#include "skills/windows/WindowControlSkill.h"
#include "skills/windows/WindowLayoutSkill.h"

int main() {
    SkillRegistry registry;
    registry.registerSkill(std::make_unique<OpenAppSkill>());
    registry.registerSkill(std::make_unique<VolumeSetSkill>());
    registry.registerSkill(std::make_unique<WebOpenSkill>());
    registry.registerSkill(std::make_unique<WebSearchSkill>());
    registry.registerSkill(std::make_unique<WindowControlSkill>());
    registry.registerSkill(std::make_unique<WindowLayoutSkill>());

    const std::string inputText{
        std::istreambuf_iterator<char>(std::cin),
        std::istreambuf_iterator<char>()
    };

    SkillResult result;
    try {
        const nlohmann::json input = nlohmann::json::parse(inputText);
        Executor executor(registry);
        result = executor.execute(input);
    } catch (const nlohmann::json::parse_error& error) {
        result = SkillResult::fail(
            nullptr,
            nullptr,
            "Invalid JSON",
            "INVALID_JSON",
            error.what()
        );
    } catch (const std::exception& error) {
        result = SkillResult::fail(
            nullptr,
            nullptr,
            "Internal error",
            "INTERNAL_ERROR",
            error.what()
        );
    }

    std::cout << result.toJson().dump(2) << std::endl;
    return 0;
}
