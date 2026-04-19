# Graph Report - graph-task-005ea528-8e62-4d29-b176-d64134185905  (2026-04-19)

## Corpus Check
- Corpus is ~8,933 words - fits in a single context window. You may not need a graph.

## Summary
- 59 nodes · 64 edges · 3 communities detected
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 1.0)
- Token cost: 18,972 input · 9,600 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]

## God Nodes (most connected - your core abstractions)
1. `pdf-8c773b1d-4e44-4430-ab07-d2b63fe044e0` - 58 edges
2. `Fan Connector J13` - 4 edges
3. `NVIDIA Corporation` - 4 edges
4. `CAN Bus Header J17` - 2 edges
5. `RTC Backup Battery Connector J3` - 2 edges
6. `DC Power Jack J16` - 2 edges
7. `Jetson Orin Nano` - 2 edges
8. `NVIDIA Orin` - 2 edges
9. `DisplayPort` - 2 edges
10. `PoE Header J19` - 1 edges

## Surprising Connections (you probably didn't know these)
- `pdf-8c773b1d-4e44-4430-ab07-d2b63fe044e0` --mentions--> `CAN Bus Header J17`  [EXTRACTED]
  raw/pdf-8c773b1d-4e44-4430-ab07-d2b63fe044e0.pdf → raw/pdf-8c773b1d-4e44-4430-ab07-d2b63fe044e0.pdf  _Bridges community 0 → community 1_
- `pdf-8c773b1d-4e44-4430-ab07-d2b63fe044e0` --mentions--> `NVIDIA Corporation`  [EXTRACTED]
  raw/pdf-8c773b1d-4e44-4430-ab07-d2b63fe044e0.pdf → raw/pdf-8c773b1d-4e44-4430-ab07-d2b63fe044e0.pdf  _Bridges community 0 → community 2_

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (51): pdf-8c773b1d-4e44-4430-ab07-d2b63fe044e0, Jetson Orin Nano Developer Kit Carrier Board, UART1 Interface, UART2 DEBUG Interface, Button Header J14, SYS_RESET Signal, FORCE_RECOVERY Signal, SLEEP/WAKE Signal (+43 more)

### Community 1 - "Community 1"
Cohesion: 0.5
Nodes (4): CAN Bus Header J17, Fan Connector J13, RTC Backup Battery Connector J3, DC Power Jack J16

### Community 2 - "Community 2"
Cohesion: 0.5
Nodes (4): DisplayPort, Jetson Orin Nano, NVIDIA Corporation, NVIDIA Orin

## Knowledge Gaps
- **50 isolated node(s):** `PoE Header J19`, `Backpower Header J18`, `VDD_5V_SYS Power Rail`, `VDD_3V3_SYS Power Rail`, `VDD_1V8 Power Rail` (+45 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `pdf-8c773b1d-4e44-4430-ab07-d2b63fe044e0` connect `Community 0` to `Community 1`, `Community 2`?**
  _High betweenness centrality (0.995) - this node is a cross-community bridge._
- **Why does `Fan Connector J13` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Why does `NVIDIA Corporation` connect `Community 2` to `Community 0`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Fan Connector J13` (e.g. with `CAN Bus Header J17` and `RTC Backup Battery Connector J3`) actually correct?**
  _`Fan Connector J13` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `NVIDIA Corporation` (e.g. with `Jetson Orin Nano` and `NVIDIA Orin`) actually correct?**
  _`NVIDIA Corporation` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PoE Header J19`, `Backpower Header J18`, `VDD_5V_SYS Power Rail` to the rest of the system?**
  _50 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.04 - nodes in this community are weakly interconnected._