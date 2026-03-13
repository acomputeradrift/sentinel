
# Device Testing Web Application
## Architecture Specification

---

# 1. Purpose

This system provides a browser-based testing interface used to verify the behavior of a smart home installation.

The application:

- mirrors the real smart home device interface
- allows technicians to navigate the same device pages
- records pass / fail results while the technician operates the real system
- stores results historically and append-only

The testing application does not control any devices.
All actions occur on the real smart home system, and the application records the outcome.

---

# 2. System Roles

The system supports two roles using separate browser windows.

## Site Technician

Uses the testing window.

Responsibilities:

- operate the real smart home system
- navigate the testing interface
- record pass / fail results

The technician interface never displays diagnostics.

## Remote Programmer

Uses the diagnostics window.

Responsibilities:

- upload project files
- trigger extraction
- trigger regeneration
- review failed tests
- use diagnostic references to locate programming issues

---

# 3. Project Model

Testing is organized using the following structure.

Project
   ├── Events
   └── Devices
          ├── Page
          │      └── Control / Button
          │             └── Test Targets
          └── Page

## Project

Represents a single installation or job.

Contains:

- events
- devices

## Events

Events belong directly to the project.

They are:

- not device-based
- not page-based

## Devices

Each project may contain multiple devices.

Each device contains pages that mirror the real device interface.

## Pages

Pages group controls within a device.

The testing interface uses the same page IDs extracted from the project when building the device pages.

If a control in the real smart home device is programmed to navigate to a target page, the testing interface uses the extracted target page link for that control to navigate to the corresponding page in the app.

This allows the testing interface to mimic the programmed page navigation behavior of the real smart home device while remaining separate from it.

## Controls / Buttons

Controls represent real interface buttons on the device.

These buttons are used by the technician to verify system behavior.

## Test Targets

Test targets belong to a control.

A control may contain multiple test targets.

Each test target represents a verification point that must be confirmed during testing.

---

# 4. Extraction

Project files are converted into a canonical JSON project model.

Extraction produces:

- project structure
- events
- devices
- pages
- controls
- test targets
- page navigation relationships
- diagnostic references

Extraction is defined by:

`apex_project_structure.json`

This file defines how project elements are mapped into the JSON model.

---

# 5. Extracted Data Types

## UI Data

UI data defines the testing interface structure.

Includes:

- devices
- pages
- controls
- test targets
- page navigation relationships

## Diagnostic Data

Diagnostic data consists of project-file references extracted directly from the project.

This data is never inferred or generated.

Examples include:

- scope references
- macro names
- variable names
- driver commands
- project file paths

Diagnostic data provides a direct reference to the programming elements associated with a control.

---

# 6. Web Application Structure

The browser system consists of two separate interfaces.

## Testing Window

Used by the technician.

Characteristics:

- single-project interface
- accessed through a direct project link
- mimics the real device interface
- records pass / fail results
- contains no diagnostic information

## Diagnostics Window

Used by the programmer.

Functions:

- project upload
- extraction
- regeneration
- viewing test results
- accessing diagnostic references

---

# 7. Device Viewer

Each device is rendered in a device viewer interface.

The viewer contains:

- a device shell
- a dynamic content window

Pages are rendered inside the content window.

---

# 8. Page Rendering

Devices may contain large numbers of pages.

To maintain performance:

- only one page is rendered at a time
- pages are rendered on demand
- previously rendered pages are cleared when navigation occurs

---

# 9. Page Navigation

Page navigation is based on page IDs and target page relationships extracted from the project.

For each control that causes page navigation in the real smart home device, the testing interface uses the same extracted page relationship in the app.

The app does not read navigation from the live device.
It uses the extracted project data to reproduce that navigation behavior.

---

# 10. Change Detection

When a project file is updated:

1. the project is reloaded
2. extraction runs again
3. the new JSON model is compared to the previous model
4. regeneration occurs only where changes exist

---

# 11. Test Result Storage

Test results are stored separately from the project model.

Results include:

- timestamp
- device reference
- page reference
- control reference
- pass / fail result

Test results are append-only.

---

# 12. Data Persistence

Test data must survive:

- project reload
- extraction
- regeneration

Regeneration never deletes historical test results.

Results reference stable identifiers within the project model.

---

# 13. Project Upload and Regeneration

Project upload occurs in the diagnostics window.

The programmer performs:

1. project upload
2. extraction
3. regeneration

After regeneration, the testing interface refreshes to reflect the updated project structure.

---

# 14. Data Flow

Project File
     │
     ▼
Upload (Diagnostics Window)
     │
     ▼
Extraction (apex_project_structure.json)
     │
     ▼
Project JSON Model
     │
     ▼
Testing Interface
     │
     ▼
Technician Testing
     │
     ├── Pass → Stored
     │
     └── Fail → Visible in Diagnostics Window
                        │
                        ▼
              Programmer Investigation
                        │
                        ▼
                Project File Update
                        │
                        ▼
                Re-Upload (Diagnostics Window)
                        │
                        ▼
                   Re-Extraction
                        │
                        ▼
                   Regeneration
                        │
                        ▼
              Testing Interface Refresh
                        │
                        ▼
                Testing Continues

---

# 15. System Principles

1. The testing application never controls devices
2. The testing interface mimics the real device interface
3. Diagnostics are never shown to the technician
4. Diagnostic data is always extracted from project files
5. Diagnostic data is never inferred
6. Test results are append-only
7. Test results persist across regeneration
8. Only the active page is rendered
9. Page navigation follows extracted page relationships from the project
