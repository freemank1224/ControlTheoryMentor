# Graph Report - graph-task-2e660eef-033c-4d06-8fe3-15e9ef3300b8  (2026-04-19)

## Corpus Check
- Corpus is ~8,933 words - fits in a single context window. You may not need a graph.

## Summary
- 50 nodes · 49 edges · 1 communities detected
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 18,925 input · 9,600 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]

## God Nodes (most connected - your core abstractions)
1. `pdf-f77b039b-0149-4dd4-be35-96f2ae824c51` - 49 edges
2. `Jetson Orin Nano Developer Kit Carrier Board Specification` - 1 edges
3. `Jetson Orin Nano Module` - 1 edges
4. `Carrier Board` - 1 edges
5. `USB Ports` - 1 edges
6. `Gigabit Ethernet` - 1 edges
7. `DisplayPort Connector J8` - 1 edges
8. `M.2 Key E Expansion Slot J10` - 1 edges
9. `M.2 Key M Expansion Slot` - 1 edges
10. `Camera Connectors J20 J21` - 1 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (50): pdf-f77b039b-0149-4dd4-be35-96f2ae824c51, CAN Bus Header J17, GPIO08 Fan Tach, GPIO14 Fan PWM, PM IC_BBAT, VDD_5V_SYS, VDD_3V3_SYS, DC_IN (+42 more)

## Knowledge Gaps
- **49 isolated node(s):** `Jetson Orin Nano Developer Kit Carrier Board Specification`, `Jetson Orin Nano Module`, `Carrier Board`, `USB Ports`, `Gigabit Ethernet` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `Jetson Orin Nano Developer Kit Carrier Board Specification`, `Jetson Orin Nano Module`, `Carrier Board` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.04 - nodes in this community are weakly interconnected._