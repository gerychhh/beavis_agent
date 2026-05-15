#pragma once

#include <nlohmann/json.hpp>

struct RuntimeContext {
    bool dryRun = true;
    nlohmann::json toolMeta = nlohmann::json::object();
};
