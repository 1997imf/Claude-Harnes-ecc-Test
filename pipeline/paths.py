"""Where every file of a video project lives.

projects/<slug>/
├── brief.json            input written by you
├── manifest.json         pipeline state
├── storyboard.json       plan stage
├── scene/scene.json      render stage (parameters for the Manim template)
├── renders/              render stage (git-ignored)
│   ├── secant_tangent.mp4
│   ├── render_facts.json
│   ├── render.log
│   └── manim_media/      Manim's own working files
├── qa_report.json        quality_check stage
├── preview.html          package stage
└── metadata.json         package stage (title, description, tags for publishing)
"""

from dataclasses import dataclass
from pathlib import Path

BRIEF_FILENAME = "brief.json"
VIDEO_FILENAME = "secant_tangent.mp4"


@dataclass(frozen=True)
class ProjectPaths:
    project_dir: Path
    brief: Path

    @classmethod
    def from_brief(cls, brief_path: Path) -> "ProjectPaths":
        brief_path = Path(brief_path).resolve()
        return cls(project_dir=brief_path.parent, brief=brief_path)

    @classmethod
    def from_project_dir(cls, project_dir: Path) -> "ProjectPaths":
        project_dir = Path(project_dir).resolve()
        return cls(project_dir=project_dir, brief=project_dir / BRIEF_FILENAME)

    @property
    def manifest(self) -> Path:
        return self.project_dir / "manifest.json"

    @property
    def storyboard(self) -> Path:
        return self.project_dir / "storyboard.json"

    @property
    def scene_params(self) -> Path:
        return self.project_dir / "scene" / "scene.json"

    @property
    def renders_dir(self) -> Path:
        return self.project_dir / "renders"

    @property
    def manim_media_dir(self) -> Path:
        return self.renders_dir / "manim_media"

    @property
    def video(self) -> Path:
        return self.renders_dir / VIDEO_FILENAME

    @property
    def render_facts(self) -> Path:
        return self.renders_dir / "render_facts.json"

    @property
    def render_log(self) -> Path:
        return self.renders_dir / "render.log"

    @property
    def qa_report(self) -> Path:
        return self.project_dir / "qa_report.json"

    @property
    def preview(self) -> Path:
        return self.project_dir / "preview.html"

    @property
    def metadata(self) -> Path:
        return self.project_dir / "metadata.json"

    def relative(self, path: Path) -> str:
        """Path relative to the project folder, as stored in the manifest."""
        return path.relative_to(self.project_dir).as_posix()
