# Changelog

All notable changes to the H2Track project will be documented in this file.

## [1.0.0] - 2026-04-17

### Added

#### Core Features
- **Gas Source Localization**: Surge-Cast algorithm with wind-aware navigation
- **Particle Filter**: Probabilistic source localization with Gaussian plume model
- **Algorithm Fusion**: Weighted/switching/cascade fusion of Surge-Cast and PF
- **Wind Estimation**: Infers wind direction from concentration gradients

#### Multi-Gas Support
- Hydrogen (H2): Rising gas, elevated sensor at 1.5m
- Methane (CH4): Rising gas, sensor at 1.2m
- Carbon Monoxide (CO): Neutral buoyancy, sensor at 0.5m
- Propane (C3H8): Sinking gas, low sensor at 0.3m

#### Navigation
- Nav2 integration for autonomous navigation
- SLAM support with slam_toolbox
- Costmap-based obstacle avoidance
- Patrol and tracking modes

#### Simulation
- GADEN integration for realistic gas dispersion
- Gazebo simulation environment
- Multiple scene configurations (warehouse, baseline)

#### Evaluation Framework
- Benchmark scene for algorithm comparison
- Tracking metrics (distance error, time to source)
- Baseline algorithms (Gradient Search, Random Walk, Spiral Search)

#### Multi-Robot Coordination (Experimental)
- Coordinator node for multi-robot coordination
- Role assignment (Tracker, Explorer, Verifier)
- Distributed information fusion

#### Web Console
- Real-time metrics dashboard
- 3D heatmap visualization
- Scene selector
- Gas concentration monitoring

### Performance
- Surge-Cast: < 0.1ms per update
- Wind Estimator: < 0.2ms per update
- Fusion: < 0.05ms per update
- 117 unit tests passing

### Documentation
- CLAUDE.md: Comprehensive development guide
- research_roadmap.md: Publication roadmap
- theory_analysis.md: Convergence proofs framework
- multi_robot_design.md: Multi-robot architecture

### Tested Scenarios
- Warehouse environment with GADEN gas simulation
- Hydrogen source tracking (successful)
- Mode transitions (PATROL → SEEK_CONFIRM → SEEK_TRACK → SOURCE_FOUND)

### Latest Updates (2026-04-17)

#### Added
- RViz visualization configuration (gas_tracking.rviz)
- CONTRIBUTING.md with development guidelines
- Integration tests for complete tracking pipeline
- Adaptive step size tests
- Requirements.txt for easy setup
- Simulation test script

#### Fixed
- Nav2 NavigateToPose Action client integration
- README documentation test failures
- Integration tests to match actual API

#### Improved
- Theory analysis with convergence proofs
- Algorithm complexity analysis
- Test coverage (1145+ tests, 99.9% pass rate)

#### Performance
- Surge-Cast: 0.027ms per update
- Wind Estimator: 0.8ms per update
- Fusion: 0.005ms per update

### Known Limitations
- Multi-robot coordination requires further testing
- Real-world deployment needs additional work
- Theory proofs need mathematical rigor

### Future Work
- Phase 1: Complete theoretical analysis
- Phase 2: Multi-robot testing
- Phase 3: Sim-to-real transfer
- Phase 4: Real-world experiments
- Phase 5: Publication preparation

## [0.1.0] - 2026-03-15

### Added
- Initial project structure
- Basic tracking algorithms
- Gazebo simulation setup
