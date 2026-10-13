I want to build an automated AI-powered educational video production pipeline, starting with math videos using Manim and eventually supporting end-to-end YouTube publishing.

## Current environment

- Project repository: `Claude-Harnes-Test`
- Existing Manim project: `animations/secant_tangent/`
- Python 3.13 virtual environment exists inside `animations/secant_tangent/.venv`
- Manim Community Edition 0.22.0 is installed and has successfully rendered the `SecantTangent` scene.
- This project is on a Mac. Do not assume administrator access.
- An ECC (Everything Claude Code) setup may exist in the repository. Inspect the repository before making changes.

## Long-term goal

Eventually, I want to enter a topic and have the pipeline:

1. Research and plan an educational video.
2. Create an accurate script and scene-by-scene storyboard.
3. Generate Manim animation code.
4. Render the animation in high quality.
5. Generate narration and synchronize it with the animation.
6. Add captions, sound, and other editing elements.
7. Check mathematical correctness, visual quality, and audio synchronization.
8. Generate a title, description, and thumbnail.
9. Show me a preview and request my approval.
10. Upload the approved video to YouTube, with optional scheduling.

## Your task: inspect and plan first

Do not immediately implement the entire system.

First:

1. Inspect the repository structure, README, `.gitignore`, existing Manim source, installed Python environment, and available rendering tools.
2. Identify reusable code and avoid duplicating existing functionality.
3. Propose a modular architecture for the complete pipeline.
4. Explain how the pipeline will pass data between stages and recover from failures.
5. Identify which features can run locally and which require external APIs, credentials, or additional software.
6. Recommend a practical MVP that can be completed and tested before implementing narration, editing, or uploading.
7. Present a phased implementation plan with clear acceptance tests.

## Important constraints

- Do not delete or overwrite existing working files.
- Do not modify the existing `SecantTangent` scene unless I explicitly approve it.
- Keep the future automation code separate from the existing animation project.
- Do not install packages or system software before explaining why they are needed.
- Do not assume that access to Claude Code automatically grants programmatic API access.
- Never put API keys, OAuth tokens, or credentials into source code or Git.
- Treat AI-generated code as untrusted: validate it, limit automatic retries, and avoid unrestricted shell execution.
- Do not enable YouTube uploads yet.
- The eventual publishing stage must require my explicit approval before uploading or scheduling a video.
- Keep the first version simple and understandable for a beginner who is learning Python and AI development.

## First response

For now, only inspect the environment and present your findings, proposed architecture, and MVP plan. Do not create, edit, delete, install, commit, or upload anything until I approve the plan.