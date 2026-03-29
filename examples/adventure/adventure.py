from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAP_PATH = Path(__file__).parent / "adventure-map.json"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "we",
    "what",
    "you",
    "your",
}


@dataclass
class ActionRecord:
    action_id: str
    phrases: list[str]
    response: str
    effects: list[str]


@dataclass
class CorpusExample:
    phrase: str
    assistant: str
    phrase_terms: list[str]


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _parse_value(raw: str) -> Any:
    low = raw.lower().strip()
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", raw.strip()):
        return int(raw.strip())
    return raw.strip()


def _ordered_terms(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return [w for w in words if len(w) >= 3 and w not in STOPWORDS]


def _build_dynamic_hints(examples: list[CorpusExample]) -> dict[str, set[str]]:
    """Build lightweight related-term hints from the current JIT corpus only."""
    hints: dict[str, set[str]] = {}
    for ex in examples:
        terms = set(ex.phrase_terms)
        for term in terms:
            others = terms - {term}
            if not others:
                continue
            bucket = hints.setdefault(term, set())
            bucket.update(others)
    return hints


def _expand_terms_with_hints(terms: list[str], hints: dict[str, set[str]]) -> list[str]:
    expanded = list(terms)
    for term in terms:
        expanded.extend(sorted(hints.get(term, set())))
    return expanded


def _expanded_terms(text: str, hints: dict[str, set[str]]) -> list[str]:
    return _expand_terms_with_hints(_ordered_terms(text), hints)


def _parse_corpus_examples(corpus_snippets: list[str]) -> list[CorpusExample]:
    examples: list[CorpusExample] = []
    for snippet in corpus_snippets:
        lines = [line.strip() for line in snippet.splitlines() if line.strip()]
        phrase = ""
        assistant = ""
        for line in lines:
            if line.lower().startswith("user:"):
                phrase = line.split(":", 1)[1].strip()
            if line.lower().startswith("assistant:"):
                assistant = line.split(":", 1)[1].strip()
        if not phrase or not assistant:
            continue
        examples.append(
            CorpusExample(
                phrase=phrase,
                assistant=assistant,
                phrase_terms=_ordered_terms(phrase),
            )
        )
    return examples


def _bm25_score(
    query_terms: list[str],
    doc_counts: Counter[str],
    doc_len: int,
    doc_freqs: dict[str, int],
    num_docs: int,
    avg_len: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    score = 0.0
    for term in query_terms:
        tf = float(doc_counts.get(term, 0))
        if tf <= 0.0:
            continue
        df = float(doc_freqs.get(term, 0))
        idf = math.log(1.0 + ((num_docs - df + 0.5) / (df + 0.5))) if num_docs > 0 else 0.0
        denom = tf + k1 * (1.0 - b + b * (doc_len / max(1.0, avg_len)))
        score += idf * ((tf * (k1 + 1.0)) / max(1e-9, denom))
    return score


def _generate_from_corpus(user_text: str, corpus_snippets: list[str]) -> str:
    """Standalone tiny generator: retrieve best assistant sentence from JIT corpus."""
    examples = _parse_corpus_examples(corpus_snippets)
    if not examples:
        return "I am not sure what outcome applies here."

    hints = _build_dynamic_hints(examples)

    query_raw_terms = _ordered_terms(user_text)
    query_terms = _expanded_terms(user_text, hints)
    if not query_terms:
        return "I am not sure what outcome applies here."

    doc_freqs: dict[str, int] = {}
    lengths: list[int] = []
    docs: list[tuple[Counter[str], int]] = []
    for ex in examples:
        ex_terms = _expand_terms_with_hints(ex.phrase_terms, hints)
        counts = Counter(ex_terms)
        docs.append((counts, len(ex_terms)))
        lengths.append(len(ex_terms))
        for term in set(ex_terms):
            doc_freqs[term] = doc_freqs.get(term, 0) + 1

    avg_len = (sum(lengths) / len(lengths)) if lengths else 1.0
    num_docs = len(examples)

    best_score = -1.0
    second_score = -1.0
    best_overlap = 0
    best = examples[0].assistant
    for ex, (counts, doc_len) in zip(examples, docs):
        ex_terms = _expand_terms_with_hints(ex.phrase_terms, hints)
        bm25 = _bm25_score(query_terms, counts, doc_len, doc_freqs, num_docs, avg_len)
        raw_overlap = len(set(query_raw_terms) & set(ex.phrase_terms))
        overlap = len(set(query_terms) & set(ex_terms))
        # Prefer exact raw overlap first, then expanded overlap, then lexical score.
        score = (raw_overlap * 1.6) + (overlap * 0.6) + (bm25 * 1.0)
        if score > best_score:
            second_score = best_score
            best_score = score
            best_overlap = raw_overlap
            best = ex.assistant
        elif score > second_score:
            second_score = score

    # Reject low-confidence matches so we avoid accidental action execution.
    margin = best_score - second_score
    if best_overlap <= 0 and best_score < 1.25:
        return "No outcome could be inferred from that input."
    if best_score < 1.05:
        return "No outcome could be inferred from that input."
    if margin < 0.06 and best_score < 1.6:
        return "No outcome could be inferred from that input."

    return best


def _get_path(root: dict[str, Any], path: str) -> Any:
    node: Any = root
    for key in path.split("."):
        if isinstance(node, dict):
            if key not in node:
                return None
            node = node[key]
            continue
        if isinstance(node, list):
            found = None
            for item in node:
                if isinstance(item, dict) and item.get("id") == key:
                    found = item
                    break
            if found is None:
                return None
            node = found
            continue
        return None
    return node


def _set_path(root: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    node: Any = root
    for key in keys[:-1]:
        if isinstance(node, dict):
            if key not in node:
                node[key] = {}
            node = node[key]
            continue

        if isinstance(node, list):
            found = None
            for item in node:
                if isinstance(item, dict) and item.get("id") == key:
                    found = item
                    break
            if found is None:
                return
            node = found
            continue

        return

    last = keys[-1]
    if isinstance(node, dict):
        node[last] = value


def _check_requirement(state: dict[str, Any], req: str) -> bool:
    # req format: op:path:value
    try:
        op, path, raw_value = req.split(":", 2)
    except ValueError:
        return False

    actual = _get_path(state, path)
    expected = _parse_value(raw_value)

    if op == "eq":
        return actual == expected
    if op == "has":
        return isinstance(actual, list) and expected in actual
    if op == "gte":
        return isinstance(actual, int) and isinstance(expected, int) and actual >= expected
    return False


def _apply_effect(state: dict[str, Any], effect: str) -> None:
    # effect formats:
    # set:path:value
    # add:path:value (list append if missing)
    # remove:path:value (list remove if present)
    # inc:path:delta (int add)
    try:
        op, path, raw_value = effect.split(":", 2)
    except ValueError:
        return

    value = _parse_value(raw_value)

    if op == "set":
        _set_path(state, path, value)
        return

    if op == "inc":
        current = _get_path(state, path)
        if isinstance(current, int) and isinstance(value, int):
            _set_path(state, path, current + value)
        return

    if op == "add":
        current = _get_path(state, path)
        if isinstance(current, list) and value not in current:
            current.append(value)
        return

    if op == "remove":
        current = _get_path(state, path)
        if isinstance(current, list) and value in current:
            current.remove(value)


def _location_index(world: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {loc["id"]: loc for loc in world.get("locations", [])}


def _npc_index(world: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {npc["id"]: npc for npc in world.get("npcs", [])}


def _item_label(item_id: str) -> str:
    return item_id.replace("_", " ")


def _item_description(world: dict[str, Any], item_id: str) -> str:
    catalog = world.get("item_descriptions", {})
    if isinstance(catalog, dict):
        description = catalog.get(item_id)
        if isinstance(description, str) and description.strip():
            return description
    return f"You inspect the {_item_label(item_id)}."


def _toggle_phrase_variants(base_item_label: str) -> tuple[list[str], list[str]]:
    on_phrases = [
        f"turn on {base_item_label}",
        f"turn {base_item_label} on",
        f"switch on {base_item_label}",
        f"switch {base_item_label} on",
        f"enable {base_item_label}",
        f"activate {base_item_label}",
    ]
    off_phrases = [
        f"turn off {base_item_label}",
        f"turn {base_item_label} off",
        f"switch off {base_item_label}",
        f"switch {base_item_label} off",
        f"disable {base_item_label}",
        f"deactivate {base_item_label}",
    ]
    return on_phrases, off_phrases


def _build_item_rule_actions(world: dict[str, Any]) -> list[ActionRecord]:
    actions: list[ActionRecord] = []
    for rule in world.get("item_rules", []):
        if not isinstance(rule, dict):
            continue
        rule_type = str(rule.get("type", "")).lower().strip()
        if rule_type == "toggle":
            actions.extend(_toggle_rule_actions(world, rule))
        elif rule_type == "transform":
            actions.extend(_transform_rule_actions(world, rule))
    return actions


def _toggle_rule_actions(world: dict[str, Any], rule: dict[str, Any]) -> list[ActionRecord]:
    item = str(rule.get("item", "")).strip()
    if not item:
        return []

    holder_path = str(rule.get("holder_path", "player.inventory"))
    state_path = str(rule.get("state_path", f"world.item_states.{item}.is_on"))
    label = _item_label(item)
    currently_on = _to_bool(_get_path(world, state_path), default=False)

    base_requires = [str(x) for x in rule.get("requires", []) if isinstance(x, str)]
    has_item_req = f"has:{holder_path}:{item}"
    if not all(_check_requirement(world, req) for req in base_requires):
        return []

    has_item = _check_requirement(world, has_item_req)
    default_on, default_off = _toggle_phrase_variants(label)

    if not has_item:
        unavailable_phrases = [
            str(x)
            for x in rule.get("unavailable_phrases", default_on + default_off)
            if isinstance(x, str)
        ]
        unavailable_response = str(
            rule.get("unavailable_response", f"You need to pick up the {label} first.")
        )
        return [
            ActionRecord(
                action_id=f"toggle_unavailable__{item}",
                phrases=unavailable_phrases,
                response=unavailable_response,
                effects=[],
            )
        ]

    if currently_on:
        phrases = [
            str(x)
            for x in rule.get(
                "off_phrases",
                default_off,
            )
            if isinstance(x, str)
        ]
        response = str(rule.get("off_response", f"You turn off the {label}."))
        effects = [f"set:{state_path}:false"]
        effects.extend([str(x) for x in rule.get("off_effects", []) if isinstance(x, str)])
        return [
            ActionRecord(
                action_id=f"toggle_off__{item}",
                phrases=phrases,
                response=response,
                effects=effects,
            )
        ]

    phrases = [
        str(x)
        for x in rule.get(
            "on_phrases",
            default_on,
        )
        if isinstance(x, str)
    ]
    response = str(rule.get("on_response", f"You turn on the {label}."))
    effects = [f"set:{state_path}:true"]
    effects.extend([str(x) for x in rule.get("on_effects", []) if isinstance(x, str)])
    return [
        ActionRecord(
            action_id=f"toggle_on__{item}",
            phrases=phrases,
            response=response,
            effects=effects,
        )
    ]


def _transform_rule_actions(world: dict[str, Any], rule: dict[str, Any]) -> list[ActionRecord]:
    source_item = str(rule.get("from", "")).strip()
    target_item = str(rule.get("to", "")).strip()
    if not source_item or not target_item:
        return []

    source_path = str(rule.get("source_path", "player.inventory"))
    target_path = str(rule.get("target_path", source_path))

    base_requires = [str(x) for x in rule.get("requires", []) if isinstance(x, str)]
    has_source_req = f"has:{source_path}:{source_item}"
    has_target_req = f"has:{target_path}:{target_item}"

    source_label = _item_label(source_item)
    target_label = _item_label(target_item)
    phrases = [
        str(x)
        for x in rule.get(
            "phrases",
            [
                f"transform {source_label}",
                f"convert {source_label}",
            ],
        )
        if isinstance(x, str)
    ]
    response = str(rule.get("response", f"You turn {source_label} into {target_label}."))

    actions: list[ActionRecord] = []

    if all(_check_requirement(world, req) for req in (base_requires + [has_source_req])):
        effects: list[str] = []
        if _to_bool(rule.get("consume_source", True), default=True):
            effects.append(f"remove:{source_path}:{source_item}")
        if _to_bool(rule.get("add_target", True), default=True):
            effects.append(f"add:{target_path}:{target_item}")
        effects.extend([str(x) for x in rule.get("effects", []) if isinstance(x, str)])

        actions.append(
            ActionRecord(
                action_id=f"transform__{source_item}__{target_item}",
                phrases=phrases,
                response=response,
                effects=effects,
            )
        )

    already_done_response = rule.get("already_done_response")
    if isinstance(already_done_response, str) and already_done_response.strip():
        source_present = _check_requirement(world, has_source_req)
        target_present = _check_requirement(world, has_target_req)
        if (not source_present) and target_present and all(
            _check_requirement(world, req) for req in base_requires
        ):
            done_phrases = [
                str(x)
                for x in rule.get("already_done_phrases", phrases)
                if isinstance(x, str)
            ]
            done_effects = [
                str(x) for x in rule.get("already_done_effects", []) if isinstance(x, str)
            ]
            actions.append(
                ActionRecord(
                    action_id=f"transform_done__{source_item}__{target_item}",
                    phrases=done_phrases,
                    response=str(already_done_response),
                    effects=done_effects,
                )
            )

    return actions


def _describe_location(world: dict[str, Any]) -> str:
    locations = _location_index(world)
    npcs = _npc_index(world)
    player_loc = world["player"]["location"]
    loc = locations[player_loc]

    exit_labels: list[str] = []
    for exit_row in loc.get("exits", []):
        direction = str(exit_row["name"])
        destination = str(locations[exit_row["to"]]["name"])
        exit_labels.append(f"{destination} ({direction})")
    exits = ", ".join(exit_labels) if exit_labels else "none"
    npcs_here = [npc["name"] for npc in npcs.values() if npc.get("location") == player_loc]
    npc_text = ", ".join(npcs_here) if npcs_here else "nobody"
    items_here = loc.get("items", []) if isinstance(loc.get("items", []), list) else []
    item_text = ", ".join(_item_label(item) for item in items_here) if items_here else "none"

    return (
        f"{loc['name']}: {loc['description']} Exits: {exits}. "
        f"People here: {npc_text}. Items here: {item_text}."
    )


def _build_jit_actions(world: dict[str, Any]) -> list[ActionRecord]:
    locations = _location_index(world)
    npcs = _npc_index(world)
    player_loc = world["player"]["location"]
    loc = locations[player_loc]

    actions: list[ActionRecord] = []

    # Global interactions (look, inspect, inventory, etc.) are fully data-driven.
    for interaction in world.get("global_interactions", []):
        requires = interaction.get("requires", [])
        if all(_check_requirement(world, req) for req in requires):
            actions.append(
                ActionRecord(
                    action_id=interaction["id"],
                    phrases=list(interaction.get("phrases", [])),
                    response=interaction["response"],
                    effects=list(interaction.get("effects", [])),
                )
            )

    # Generic item rules (toggle/transform) are data-driven from JSON.
    actions.extend(_build_item_rule_actions(world))

    # Generic inspect actions for nearby/held items.
    loc_items = loc.get("items", []) if isinstance(loc.get("items", []), list) else []
    inv_items = world.get("player", {}).get("inventory", [])
    visible_items = {str(item) for item in (loc_items + inv_items) if isinstance(item, str)}
    for item in sorted(visible_items):
        label = _item_label(item)
        actions.append(
            ActionRecord(
                action_id=f"inspect_item__{item}",
                phrases=[
                    f"look at {label}",
                    f"inspect {label}",
                    f"examine {label}",
                    f"check {label}",
                ],
                response=_item_description(world, item),
                effects=[],
            )
        )

    # Generic pickup actions from location item container.
    for item in loc.get("items", []) if isinstance(loc.get("items", []), list) else []:
        label = _item_label(item)
        words = [w for w in re.findall(r"[a-zA-Z']+", label.lower()) if len(w) >= 3]
        actions.append(
            ActionRecord(
                action_id=f"pickup__{item}",
                phrases=[
                    f"pick up {label}",
                    f"take {label}",
                    f"grab {label}",
                    f"get {label}",
                ],
                response=f"You pick up the {label}.",
                effects=[
                    f"remove:locations.{player_loc}.items:{item}",
                    f"add:player.inventory:{item}",
                ],
            )
        )
        if words:
            short = words[-1]
            actions[-1].phrases.extend(
                [
                    f"pick up {short}",
                    f"take {short}",
                    f"grab {short}",
                    f"get {short}",
                ]
            )

    # Generic drop actions from player inventory.
    for item in world.get("player", {}).get("inventory", []):
        if not isinstance(item, str):
            continue
        label = _item_label(item)
        words = [w for w in re.findall(r"[a-zA-Z']+", label.lower()) if len(w) >= 3]
        actions.append(
            ActionRecord(
                action_id=f"drop__{item}",
                phrases=[
                    f"drop {label}",
                    f"leave {label}",
                    f"put down {label}",
                ],
                response=f"You drop the {label}.",
                effects=[
                    f"remove:player.inventory:{item}",
                    f"add:locations.{player_loc}.items:{item}",
                ],
            )
        )
        if words:
            short = words[-1]
            actions[-1].phrases.extend(
                [
                    f"drop {short}",
                    f"leave {short}",
                    f"put down {short}",
                ]
            )

    # Movement actions generated from exits.
    for exit_row in loc.get("exits", []):
        exit_name = exit_row["name"]
        destination = locations[exit_row["to"]]["name"]
        destination_lower = destination.lower()
        destination_words = [w for w in re.findall(r"[a-zA-Z']+", destination_lower) if len(w) >= 3]
        actions.append(
            ActionRecord(
                action_id=f"move_{exit_name}",
                phrases=[
                    f"go {exit_name}",
                    f"walk {exit_name}",
                    f"head {exit_name}",
                    f"move {exit_name}",
                    f"go to {destination_lower}",
                    f"walk to {destination_lower}",
                    f"head to {destination_lower}",
                    f"move to {destination_lower}",
                    f"go {destination_lower}",
                    f"walk {destination_lower}",
                    f"head {destination_lower}",
                ],
                response=f"You go {exit_name} toward {destination}.",
                effects=[f"set:player.location:{exit_row['to']}"] ,
            )
        )

        # Convenience aliases for destination words (e.g. "go forest", "go pile").
        aliases: set[str] = set(destination_words)
        if destination_words:
            aliases.add(destination_words[-1])
        if len(destination_words) == 1:
            whole = destination_words[0]
            if whole.endswith("pile") and whole != "pile":
                aliases.add("pile")
                aliases.add(f"{whole[:-4]} pile".strip())
            if whole.startswith("forest") and whole != "forest":
                aliases.add("forest")

        for word in sorted(a for a in aliases if a):
            if word in {"north", "south", "east", "west"}:
                continue
            actions[-1].phrases.extend(
                [
                    f"go {word}",
                    f"go to {word}",
                    f"walk {word}",
                    f"head {word}",
                ]
            )

    # Location interactions.
    for interaction in loc.get("interactions", []):
        requires = interaction.get("requires", [])
        if all(_check_requirement(world, req) for req in requires):
            actions.append(
                ActionRecord(
                    action_id=interaction["id"],
                    phrases=list(interaction.get("phrases", [])),
                    response=interaction["response"],
                    effects=list(interaction.get("effects", [])),
                )
            )

    # NPC interactions in current location.
    for npc in npcs.values():
        if npc.get("location") != player_loc:
            continue
        for interaction in npc.get("interactions", []):
            requires = interaction.get("requires", [])
            if all(_check_requirement(world, req) for req in requires):
                actions.append(
                    ActionRecord(
                        action_id=interaction["id"],
                        phrases=list(interaction.get("phrases", [])),
                        response=interaction["response"],
                        effects=list(interaction.get("effects", [])),
                    )
                )

    return actions


def _build_jit_corpus(actions: list[ActionRecord]) -> list[str]:
    snippets: list[str] = []
    for action in actions:
        for phrase in action.phrases:
            snippets.append(
                f"user: {phrase}\nassistant: For input '{phrase}' choose outcome {action.action_id} and reply {action.response}"
            )
    return snippets


def _infer_action_from_text(
    user_text: str,
    corpus_snippets: list[str],
) -> tuple[str | None, str]:
    raw = _generate_from_corpus(user_text, corpus_snippets)
    match = re.search(r"\boutcome\s+([a-zA-Z0-9_.-]+)\b", raw, flags=re.IGNORECASE)
    action_id = match.group(1) if match else None
    return action_id, raw


def _print_status(world: dict[str, Any]) -> None:
    inv = ", ".join(world["player"]["inventory"]) or "nothing"
    gold = world["player"]["gold"]
    print(f"inventory: {inv}")
    print(f"gold: {gold}")


def run() -> int:
    world = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    completion_announced = False

    print(f"adventure: {world.get('title', 'Adventure')}")
    print(world.get("intro", ""))
    print(_describe_location(world))
    _print_status(world)
    print("Type anything. The engine will infer actions from generator output. Type /exit to exit.")

    while True:
        try:
            user_text = input("\n\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return 0

        if not user_text:
            continue
        if user_text.lower() == "/exit":
            print("bye")
            return 0

        actions = _build_jit_actions(world)
        action_by_id = {action.action_id: action for action in actions}
        corpus = _build_jit_corpus(actions)
        action_id, raw = _infer_action_from_text(user_text, corpus)
        if not action_id or action_id not in action_by_id:
            print("I am not sure how to do that right now. Try 'look' to see options.")
            continue

        action = action_by_id[action_id]
        for effect in action.effects:
            _apply_effect(world, effect)

        print(action.response)
        if action.action_id in {"look", "inspect_exits"}:
            print(_describe_location(world))
        elif action.action_id == "inventory":
            _print_status(world)
        else:
            print(_describe_location(world))
            _print_status(world)

        if "secret_map" in world["player"]["inventory"] and not completion_announced:
            print("You now hold the secret map. Proof of concept complete.")
            completion_announced = True


if __name__ == "__main__":
    raise SystemExit(run())
