# Process module

`/process/` is an authenticated, responsive visual walkthrough of Enginex's
document workflow. It appears in the application navigation on desktop and mobile.

The 20-second animation moves through five stages: document, field detection,
extraction, processing, and charts. The pipeline shows source linking, human
review, and analysis. Playback controls support pause/resume, replay, seeking,
and jumping to a settled view of any stage. Expand opens a presentation view;
Escape or Close restores the normal page.

The Process page omits the floating portfolio chatbox and its reserved space.
The EnginexAI navigation and workspace links remain available.

The supplied QR code appears beside the stage heading and stays visible throughout
the animation, including expanded view. On mobile it sits below the heading.
`core/static/core/enginex-access-qr.png` is the original supplied image, preserved
without edits. Scanning or clicking it opens the existing public Azure Container
App URL. If the public address changes, replace both the QR image and its link.

This is an illustrative explanation, not a live extraction job or a report.
The document fields and chart values are fixed examples, rendered locally by the
browser. They do not query, merge, or change portfolio data, and playback makes
no AI calls. The application continues to keep extracted contract evidence
separate from baseline chart totals. Links lead to the real Contract workspace
and EnginexAI for working with portfolio information.

The canvas uses separate desktop and mobile compositions rather than shrinking
desktop labels onto a phone. HTML controls and a text alternative provide
keyboard and screen-reader access. Reduced-motion preferences disable autoplay;
stage buttons remain available. Playback pauses its clock while the page is
hidden or the player is off screen, and stops at the end rather than looping.

Implementation: `core/process/views.py`, `core/templates/core/process.html`,
`core/static/core/process.js`, and `core/static/core/process.css`. It requires no
additional dependencies, services, or database migrations.
