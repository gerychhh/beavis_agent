#pragma once

#include <string>

#include <nlohmann/json.hpp>

struct ToolCall {
    std::string requestId;
    std::string type;
    std::string skill;
    nlohmann::json args = nlohmann::json::object();
    nlohmann::json meta = nlohmann::json::object();
};
