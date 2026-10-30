"""Write lab files strictly inside one lab directory, with explicit modes."""

from pathlib import Path, PurePosixPath

DIR_MODE = 0o755
FILE_MODE = 0o644


class Workspace:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, relative):
        rel = PurePosixPath(relative)
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise ValueError(f"lab path must stay inside the workspace: {relative!r}")
        return self.root.joinpath(*rel.parts)

    def mkdir(self, relative):
        target = self.path(relative)
        missing = [p for p in [target, *target.parents] if not p.exists()]
        for directory in reversed(missing):
            directory.mkdir()
            directory.chmod(DIR_MODE)  # 不受建置機器的 umask 影響
        return target

    def write(self, relative, content, mode=FILE_MODE):
        target = self.path(relative)
        if target.parent != self.root:
            self.mkdir(str(PurePosixPath(relative).parent))
        data = content.encode("utf-8") if isinstance(content, str) else content
        target.write_bytes(data)
        target.chmod(mode)
        return target
