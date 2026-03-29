---
name: adventure
description: Build JSON-driven text adventure games using the generic JIT corpus engine in examples/adventure/adventure.py.
---

# Adventure Game Skill

This skill explains how to build text adventures with:

- `examples/adventure/adventure.py` as the generic runtime engine
- JSON world files (for example `examples/adventure/adventure-map.json`) as the only place where game content and behavior are authored

The design goal is strict data-driven gameplay:

1. Player enters text.
2. Engine builds all currently valid actions from live world state.
3. Engine builds a just-in-time corpus from those actions.
4. Engine infers an outcome action id from the corpus response format.
5. Engine executes the selected action effects in order.
6. Loop.

No world-specific game logic should be hardcoded in the engine.

## Core Contract

The engine stays generic and reusable across worlds (forest, space trader, dungeon, etc.).

- World facts, actions, and phrasing live in JSON.
- Dynamic behavior is represented as action generation plus effect chains.
- The engine only knows generic concepts: requirements, effects, item containers, item rules, movement exits, and NPC/location interaction tables.

## Required Files

1. Runtime engine:
- `examples/adventure/adventure.py`

2. World definition JSON:
- `examples/adventure/adventure-map.json`

You can create additional worlds by copying the JSON and changing only data.

## World JSON Structure

A typical world JSON contains:

- `title`
- `intro`
- `player`
- `global_interactions`
- `item_rules`
- `item_descriptions`
- `locations`
- `npcs`
- `world`

### Player

```json
"player": {
  "location": "forest_path",
  "inventory": ["axe"],
  "gold": 0
}
```

### Locations

Each location can define:

- `id`
- `name`
- `description`
- `items` (container list)
- `exits` (direction + destination)
- `interactions` (stateful action entries)

```json
{
  "id": "forest_glade",
  "name": "Forest Glade",
  "description": "A quiet glade.",
  "items": ["raw_fish"],
  "exits": [
    {"name": "south", "to": "forest_path"},
    {"name": "east", "to": "woodpile"}
  ],
  "interactions": []
}
```

### NPCs

NPC records can hold local state and interaction lists.

```json
{
  "id": "trader",
  "name": "Traveller Trader",
  "location": "market",
  "state": {
    "needs_wood": true,
    "map_available": true
  },
  "interactions": [
    {
      "id": "sell_wood_to_trader",
      "phrases": ["sell firewood", "offer wood to traveller"],
      "response": "The trader buys your firewood and pays one gold coin.",
      "requires": [
        "has:player.inventory:firewood",
        "eq:npcs.trader.state.needs_wood:true"
      ],
      "effects": [
        "remove:player.inventory:firewood",
        "inc:player.gold:1",
        "set:npcs.trader.state.needs_wood:false"
      ]
    }
  ]
}
```

### Global Interactions

These are always considered (subject to `requires` checks), independent of location-specific interaction arrays.
Use this for look/help/inventory/meta interactions and generic hints.

```json
{
  "id": "help",
  "phrases": ["help", "what can i do", "i am stuck"],
  "response": "Try movement, inspection, and trade actions.",
  "requires": [],
  "effects": []
}
```

### Item Rules

`item_rules` allow generic item-state behavior without engine changes.

Supported rule types:

1. `toggle`
2. `transform`

#### Toggle Rule

Use for binary state changes (on/off, enabled/disabled, sealed/unsealed, powered/unpowered, etc.).

```json
{
  "type": "toggle",
  "item": "lantern",
  "holder_path": "player.inventory",
  "state_path": "world.item_states.lantern.is_on",
  "on_phrases": ["turn on lantern", "turn lantern on"],
  "off_phrases": ["turn off lantern", "turn lantern off"],
  "unavailable_phrases": ["turn on lantern", "turn lantern on"],
  "unavailable_response": "You need to pick up the lantern first.",
  "on_response": "You turn on the lantern.",
  "off_response": "You turn off the lantern.",
  "requires": []
}
```

#### Transform Rule

Use for one-way or stateful conversions (cook fish, refine ore, enchant blade, recharge cell, etc.).

```json
{
  "type": "transform",
  "from": "raw_fish",
  "to": "cooked_fish",
  "source_path": "player.inventory",
  "target_path": "player.inventory",
  "phrases": ["cook fish", "prepare fish"],
  "response": "You cook the fish over the cabin fire.",
  "already_done_response": "The fish is already cooked. You cannot uncook it.",
  "requires": ["eq:player.location:forest_cabin"],
  "consume_source": true,
  "add_target": true,
  "effects": []
}
```

## Requirement DSL

Requirement strings are evaluated by the engine before an action becomes available.

Format:

- `op:path:value`

Supported ops:

1. `eq`
2. `has`
3. `gte`

Examples:

- `eq:player.location:market`
- `has:player.inventory:axe`
- `gte:player.gold:1`
- `eq:npcs.trader.state.map_available:true`

## Effect DSL

Effect strings run in order when an action is selected.

Format:

- `op:path:value`

Supported ops:

1. `set`
2. `add`
3. `remove`
4. `inc`

Examples:

- `set:player.location:forest_glade`
- `add:player.inventory:firewood`
- `remove:locations.woodpile.items:kindling`
- `inc:player.gold:-1`

## Path Addressing Rules

Paths use dot notation and can traverse:

- dictionaries by key
- lists of objects by `id`

Examples:

- `player.inventory`
- `world.item_states.lantern.is_on`
- `locations.forest_glade.items`
- `npcs.trader.state.needs_wood`

## What the Engine Auto-Generates

At runtime, the engine auto-creates actions for:

1. Movement from location exits
2. Pickup actions for current location items
3. Drop actions for inventory items
4. Inspect actions for visible/held items
5. Item rule actions from `item_rules`
6. Global interactions
7. Location interactions
8. NPC interactions at current location

That action set becomes the JIT corpus.

## Authoring Best Practices

1. Keep phrase sets broad and explicit.
- Add several natural variants for each action.

2. Keep responses distinct across competing actions.
- Distinct wording improves outcome inference reliability.

3. Use `requires` aggressively.
- Restrict actions to the right time/place/state.

4. Prefer additive world state.
- Keep useful state in `world` and NPC `state` for future rules.

5. Use item ids in snake_case.
- Improves path consistency and text labeling.

6. Put all thematic language in JSON.
- Keep engine generic and reusable.

## Common Patterns

### Locked Gate

- Rule: `toggle` for `gate_mechanism`.
- `state_path`: `world.gates.north_open`.
- Movement requires `eq:world.gates.north_open:true`.

### Crafting

- Rule: `transform` from `iron_ore` to `refined_iron`.
- Requires location plus fuel/tool checks.

### Quest Flags

- Use `world.quests.<id>.stage` with `set` and `eq` requirements.

### NPC Trade

- NPC interactions with `has`/`gte` requirements and `remove`/`add`/`inc` effects.

## Testing Checklist

1. Syntax:

```bash
python3.12 -m py_compile examples/adventure/adventure.py
```

2. Smoke run:

```bash
python3.12 examples/adventure/adventure.py
```

3. Verify:

- movement aliases work as expected
- state-gated actions appear/disappear correctly
- item pickup/drop updates both inventory and location container
- toggle/transform rules obey requirements
- one-way transforms return proper already-done behavior when configured

## Extending to New Worlds

To create a new game such as `space-trader.json`:

1. Copy `examples/adventure/adventure-map.json`.
2. Replace location graph, NPCs, and interactions.
3. Define item rules and descriptions for the new theme.
4. Keep effect/requirement DSL consistent.
5. Run with the same engine by changing map path (or updating `MAP_PATH`).

The runtime should not need world-specific code changes if the JSON authoring is complete.
