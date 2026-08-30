import os
import sys
import datetime
import argparse

from magi.core.workspace import find_workspace_root
from magi.core.wiki_common import write_index

#: Every wiki directory that gets a generated `_index.md`. `magi init`
#: scaffolds all four and gives each one an index; this command used to
#: rebuild two of them, so `topics/` and `theses/` were maintained only by
#: whatever `magi lint --fix` happened to do to them.
WIKI_INDEX_DIRS = ("references", "concepts", "topics", "theses")


def build_index_for_dir(dir_path, title=None):
    """Rebuild one directory's `_index.md`. *title* is derived, not passed.

    The signature keeps *title* so existing callers do not break, but it is
    ignored: two renderers deriving the heading two ways is how the file ended
    up with two different headings depending on which command touched it last.
    """
    if not os.path.exists(dir_path):
        return

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    index_path = os.path.join(dir_path, "_index.md")
    if write_index(index_path, today=today, directory=dir_path):
        print(f"Built index: {index_path}")
    else:
        print(f"Index already current: {index_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi wiki reindex", description="Build index files for wiki directories")
    parser.add_argument("topic_dir", nargs="?", default=None,
                        help="Project directory path (default: the project you are in)")
    args = parser.parse_args(argv)

    topic_dir = args.topic_dir
    if topic_dir is None:
        # Every other command defaults to the surrounding workspace; requiring
        # the path here is what made the WebUI's reindex button exit 2.
        root = find_workspace_root()
        if root is None:
            parser.error("no MAGI workspace here - pass a topic directory, or cd into one")
        topic_dir = str(root)

    wiki_dir = os.path.join(topic_dir, "wiki")
    for name in WIKI_INDEX_DIRS:
        build_index_for_dir(os.path.join(wiki_dir, name))


if __name__ == "__main__":
    sys.exit(main())
