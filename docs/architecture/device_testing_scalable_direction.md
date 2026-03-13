# Device Testing Scalable Direction

## Purpose

This document defines a scalable direction for Sentinel by combining:

1. the architecture goals described in `device_testing_architecture.md`
2. the realities and constraints of the current Sentinel codebase

The goal is to describe a direction that is both:

- functionally correct for the intended testing workflow
- realistic to evolve from the current extraction and rendering model

This is a planning document. It is not a claim that all described behavior already exists in the current application.

---

## Current Baseline

The current codebase already proves several important ideas:

- project data can be extracted from an `.apex` file into a canonical JSON-like structure
- page relationships can be extracted and used for app navigation
- device pages can be rendered from extracted coordinates and test-target data
- user-facing data and diagnostics data are already separated in the extracted output

The current implementation is still limited in important ways:

- generation is centered on static HTML output
- rendering is effectively page-file based rather than application-state based
- generation is run one device at a time
- the browser output duplicates layout code, styling, and behavior in every generated page
- test-result persistence and diagnostics workflows described in the product docs are not yet implemented as a full application system

Because of that, the next architecture should preserve the current proven extraction concepts while replacing the current static rendering model with a scalable application model.

---

## Recommended Direction

Sentinel should evolve into a multi-project commissioning system with two separate browser surfaces:

1. a technician testing interface
2. a Commissioning Console

The technician testing interface is single-project.
It should open one active project at a time through a project-specific testing link.

The Commissioning Console is multi-project.
It should manage many projects across different days, support returning to incomplete projects, and issue refreshed technician links that preserve historical test results while reflecting the latest extracted project model.

Both surfaces should operate against the same extracted project model and the same append-only test-result store for the relevant project, while remaining clearly separated in what they expose to the user.

This direction keeps the strongest ideas from the original architecture note:

- the testing app never controls the real system
- the testing app mirrors the real device structure
- navigation comes from extracted project relationships
- Commissioning Console data is never mixed into the technician view
- test results are append-only and survive regeneration

---

## Core Model

The scalable model should treat one uploaded project as one logical testing session model.

Recommended structure:

Project
   - Events
   - Devices
      - Pages
         - Controls
            - Test Targets
         - Viewports
            - Frames
               - Controls
                  - Test Targets

Key rule:

- the extracted project model is the source of truth for project-derived structure
- test history is stored separately from the project model
- Sentinel-owned UI behavior remains separate from extracted project data

This keeps alignment with the current data-contract direction while making the model explicit enough for a real application.

---

## Stable Identity Requirement

The most important architectural addition is stable identity.

The future application should not rely on page order, generated file names, or display text alone for persistence and regeneration reconciliation.

This does not require a single display-identity method for controls.
User-facing control identity may still come from the most truthful extracted field available, including:

- button tag name
- button text
- both together when useful

The requirement is that persistence and reconciliation should use stable internal references rather than unstable presentation values alone.

The project model should provide stable identifiers for:

- project
- event
- device
- page
- control
- viewport
- viewport frame
- test target

These identifiers should be used consistently by:

- the testing UI
- the Commissioning Console
- result storage
- regeneration reconciliation

This is a required foundation for persistence across re-extraction and for safe scaling to large projects.

---

## Rendering Direction

The renderer should move from static multi-file generation to state-driven application rendering.

Recommended rules:

1. only one device view should be active at a time
2. only one page within that device should be rendered at a time
3. viewport frames should be treated as active sub-state within the current page
4. when page navigation occurs, the previous page view should be removed from the DOM
5. rendering should be driven by the extracted model, not by standalone generated HTML files

This is the most important scaling change.

The current static HTML approach is useful as a proof of rendering fidelity, but it should not remain the long-term application model for large projects with many devices and hundreds of pages.

---

## Navigation Model

Navigation should remain based on extracted project relationships.

That includes:

- device selection
- page selection
- page-link navigation between pages
- viewport frame changes where applicable

The application should never infer navigation from live runtime device behavior.

Instead:

- extracted page IDs and page-link relationships define legal app navigation
- Sentinel reproduces the navigation structure of the real programmed interface using extracted project data

This preserves the strongest and most correct part of the current model.

---

## Commissioning Console Separation

The system should continue to separate user-facing testing data from Commissioning Console data.

Technician interface:

- mirrors device pages
- exposes controls and test targets
- records pass / fail outcomes
- does not expose Commissioning Console information

Commissioning Console:

- uploads project files
- triggers extraction
- triggers regeneration
- manages multiple projects and their testing state over time
- returns users to previously started projects
- issues an up-to-date technician link for a selected project
- shows current and historical test results
- exposes extracted diagnostic references needed for troubleshooting

This separation should remain a non-negotiable architectural rule.

---

## Result Storage

Test results should be stored separately from the extracted project model.

Projects may remain active across multiple days.
The system must support pausing one project, working on another, and later resuming the first project without losing historical results.

Each stored result should include:

- timestamp
- project identifier
- device identifier when applicable
- page identifier when applicable
- control identifier when applicable
- test-target identifier
- result status
- fail note when required

Required rules:

- results are append-only
- regeneration never deletes historical results
- current status may be derived from history, but history is never collapsed
- an updated technician link for an existing project must continue to expose that project's prior recorded history

This matches the intended product behavior and avoids mixing operational history into extracted project data.

---

## Regeneration Strategy

Regeneration should initially be designed around correctness first, then optimization.

Recommended first-stage rule:

1. upload updated project file
2. re-run extraction for the full project model
3. validate the new model
4. reconcile retained test history using stable identifiers
5. issue or refresh the technician-facing project link
6. refresh the active application state safely

Important limitation:

- selective change-only regeneration should not be treated as a first requirement

It may become a later optimization, but only after:

- stable identifiers are proven reliable
- reconciliation rules are tested
- application state transitions are safe and explicit

This keeps the architecture realistic and lowers early implementation risk.

---

## Extraction Direction

The current extractor already captures useful project data, but the next step should make the extraction contract more explicit and more application-ready.

Recommended extraction goals:

1. preserve the current separation between user-facing and diagnostics-oriented data
2. expose stable IDs in the canonical model, not only in diagnostics branches
3. make viewport and frame structures first-class in the model
4. preserve extracted page-link relationships as structured navigation data
5. validate output against the approved contract rather than only loading template files

The extraction layer should remain strictly contract-driven and should continue to avoid inferred or guessed project data.

---

## MVVM-Oriented Application Layers

A scalable Sentinel implementation should be thought of as four layers:

1. Extraction Layer
   Converts `.apex` input into the canonical project model.

2. Project Model Layer
   Stores validated extracted structure with stable identifiers and clear separation between user-facing and diagnostics data.

3. Application Layer
   Manages project selection, active project state, active device, active page, viewport state, test recording, technician-link issuance, and regeneration refresh behavior.

4. Presentation Layer
   Renders the technician interface and Commissioning Console from application state.

This is a better long-term structure than directly generating fully self-contained page files.

This should be implemented with an MVVM-style separation:

- Model
  The extracted project data, diagnostics data, result history, and project records.

- ViewModel
  The application state and behavior that sit between raw data and the UI, including active project selection, active device/page/frame state, navigation rules, test-recording actions, result reconciliation, and technician-link lifecycle behavior.

- View
  The technician interface, the Commissioning Console, and any future client such as a tablet application.

This matters because Sentinel is expected to support multiple views over the same extracted project data source.
It also supports future clients without forcing each client to re-implement business logic directly against raw extracted JSON.

---

## Migration Path

The best path forward is incremental rather than a full rewrite all at once.

### Phase 1: Strengthen the Model

- keep the current extractor as the base
- add explicit stable identifiers across the canonical model
- make page, control, viewport, frame, and test-target identity consistent
- formalize contract validation

### Phase 2: Replace Static Page Generation

- stop treating each page as a standalone final artifact
- build a single application shell for one project
- render one active device page at a time from in-memory project data
- keep existing coordinate fidelity rules

### Phase 3: Add Result Persistence

- introduce append-only result storage separate from project extraction output
- attach results to stable identifiers
- support current status plus historical history views
- support reopening prior projects with preserved history

### Phase 4: Add Commissioning Console Surface

- expose upload, extraction, regeneration, failures, result review, project selection, and technician-link issuance in the Commissioning Console
- keep diagnostics references extracted-only and non-inferred

### Phase 5: Optimize Regeneration

- add safe reconciliation after re-extraction
- only consider partial change-based regeneration after full reload behavior is proven correct

---

## What Should Not Be Carried Forward Unchanged

The following ideas should not be treated as current truth or first-stage requirements:

- standalone generated HTML files as the long-term application model
- page order or file names as durable identity
- selective partial regeneration before stable identity and reconciliation are solved
- any assumption that the current codebase already provides the full two-window live application workflow

Removing those assumptions keeps the plan grounded in the actual state of the codebase.

---

## Recommended Planning Principles

1. Preserve what is already proven in extraction and rendering fidelity.
2. Replace what is not scalable in the current static output model.
3. Treat stable identity as foundational work, not an optional refinement.
4. Keep the Commissioning Console separate from the technician interface at all times.
5. Keep extracted project data separate from Sentinel-owned UI and result state.
6. Prioritize correctness of full-project reload and reconciliation before optimization.
7. Keep viewport and frame behavior explicit in the architecture, not hidden under generic page rendering language.
8. Keep model, view-model, and view responsibilities clearly separated so multiple clients can share the same underlying behavior safely.

---

## Conclusion

The correct scalable direction is not a larger version of the current static page generator.

The correct direction is:

- a canonical extracted project model
- stable identifiers across the testing structure
- a state-driven technician testing application per active project
- a multi-project Commissioning Console
- one active page rendered at a time
- append-only result storage separated from extracted data
- a distinct Commissioning Console for upload, regeneration, project management, and troubleshooting

This direction keeps the strongest ideas from the original architecture note while aligning them with the actual strengths, limitations, and next needs of the current Sentinel codebase.
