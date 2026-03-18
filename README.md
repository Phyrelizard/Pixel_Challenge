# LED Game / Victory Light Arcade

## Overview

This project is a custom multi-player LED arcade system built around a Raspberry Pi 4B, a Falcon pixel controller, arcade-style controllers, and multiple game modules designed for use at church events, family gatherings, seasonal parties, and other public or private events. The system is intended to be visually exciting, easy to operate, flexible enough for different age groups, and expandable over time as new games and features are added.

At a high level, the project consists of a **console application** running on the Raspberry Pi, a **viewer/display system** for the player-facing HDMI screen, and a growing set of **modular game engines** that each define their own gameplay, visual behavior, and instruction assets. The project began as an Easter-focused LED game concept, but it has intentionally evolved into a more general-purpose platform that can be reused for many different occasions under a broader arcade identity.

## Core Goals

The goals of this project are:

* Create a fun, colorful, fast-paced multiplayer LED arcade experience.
* Support multiple different games from one common console and hardware platform.
* Keep the operator interface clear and manageable during live events.
* Make the system reusable at church events, family parties, Halloween, and other community settings.
* Support a wide age range of players by tracking metrics that can later be used for fairer balancing.
* Build the project in a modular way so new games can be added without rewriting the entire console.

## Current Hardware / Platform Direction

The current system is centered on a Raspberry Pi 4B with:

* Dual HDMI outputs
* One console/operator-facing display
* One player-facing display for splash screens, instructions, countdowns, and scoreboards
* Falcon pixel output controller for LED lane control
* Arcade-style physical controls/controllers for players
* Python-based control software

The console application manages the high-level flow of the system, while the viewer is used to present visual content on the player-facing screen.

## Software Architecture

The software is moving toward a clean separation of responsibilities:

### Console Responsibilities

The console is responsible for:

* Main control UI for the operator
* Game selection
* Main splash handling
* Game-specific splash preview handling
* Instruction slide control
* Scoreboard generation and display timing
* Ranking visibility toggle
* Starting and pausing games
* Tracking session results and history
* Managing controller detection and button learning workflows

### Game Module Responsibilities

Each game module is responsible for:

* Gameplay rules
* Per-player state
* Timing logic
* Lane rendering logic during gameplay
* Game-specific scoring logic
* Supplying universal metrics back to the console
* Providing game-specific assets such as splash graphics and instruction slides

This structure is intended to keep the console from becoming overloaded with game-specific logic.

## Games Planned / In Progress

The current named games are:

1. **Dot Dash**
2. **Pixel Pop**
3. **Surround**
4. **Ascend**

At this stage, **Dot Dash** is the primary game under active development and serves as the first live test of the modular game framework.

## Dot Dash Summary

Dot Dash is currently the first implemented game module. The player learns two buttons and selects two colors. During gameplay, the player alternates those two buttons to move a dot forward on one lane and then return with a dash on the other lane.

Important behavior already explored or in progress includes:

* Player button-learning flow
* Color selection flow
* Countdown support
* Armed/green start state
* Reaction-time measurement
* Completion-time measurement
* Accuracy and consistency tracking
* Finish indicators and end-of-round logic

Dot Dash is also being used to validate the general framework that later games will plug into.

## Visual / Viewer Direction

The viewer is intended to remain relatively simple. The console decides what should be shown, and the viewer displays it.

The current visual direction includes:

* Main splash screen
* Game-specific splash screens when a title is selected
* Instruction slides advanced manually with the **View Intro** button
* Temporary scoreboard display
* Future generated scoreboard graphics

The scoreboard direction is a hybrid design: the console will generate a finished scoreboard image from static templates plus dynamic values, and the viewer will display the final PNG. This keeps the viewer simple and makes scoreboard rendering easier to control and debug.

## Controls / Console UI Direction

The console UI is evolving toward the following operator controls:

* **Selected Game** drop-down
* **View Scoreboard** button
* **Show Ranking** checkbox
* **View Intro** button
* **Start** button
* **Pause** button

The current design choice is that **Pause** acts as an abort/reset for timed games rather than a true resume function. This keeps gameplay fair and avoids complications with paused timing states.

## Scoreboard and Ranking Direction

The project is moving toward a universal set of metrics that all games should try to report in a consistent way.

Current universal metrics target:

* `reaction_time_sec`
* `completion_time_sec`
* `score`
* `accuracy`
* `consistency`

These metrics are intended to support both immediate round scoreboards and longer-term player profiles or ranking systems.

Ranking will likely be **always calculated** internally but **optionally displayed** depending on whether the operator enables the **Show Ranking** checkbox. This makes the project suitable for both casual public use and more competitive private/family sessions.

## What Has Been Accomplished So Far

A significant amount of foundation work has already been completed:

* Raspberry Pi OS installation and rebuild workflow established
* Backup and recovery strategy tested
* Console and viewer launch behavior restored on fresh system builds
* Falcon pixel control path verified
* Dual-display setup verified
* Base game module framework created
* Dot Dash module created and tested independently
* Dot Dash integrated into the live console environment
* Real controller button-learning flow introduced
* Temporary splash assets created for all four named games
* Console concept expanded to support scoreboards, ranking toggles, and per-game assets

## Direction Going Forward

The next major milestones for this project are:

1. Finalize Dot Dash color selection behavior and polish the per-round flow.
2. Implement real generated scoreboard graphics from console-side templates.
3. Store session and player history in a durable format such as JSON for ranking and long-term stat tracking.
4. Add richer game-specific splash and instruction assets.
5. Expand Dot Dash from single-player testing to true multi-player support.
6. Build out Pixel Pop, Surround, and Ascend using the same module framework.
7. Refine the SLA/ranking system so it is useful across different game types and age groups.

## Development Philosophy

This project is being built incrementally and tested in live hardware conditions as often as possible. The priority is not just “code that works,” but a system that is understandable, recoverable, expandable, and practical during real events with real people.

In short: this is not just one LED game. It is an arcade platform in progress.
