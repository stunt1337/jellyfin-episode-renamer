from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jellyfin_episode_renamer import build_conflict_groups, build_episode_plans, build_movie_plans, build_multi_season_episode_plans, flatten_plan, validate_plan
from media_detection import parse_movie_folder_name, parse_show_folder_name
from media_probe import tags_from_ffprobe_data
from media_tags import MediaTagOptions
from rename_ops import find_stale_source_dirs


class PlanningTests(unittest.TestCase):
    def test_media_tag_resolver_can_return_per_file_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            first = folder / "first.mkv"
            second = folder / "second.mkv"
            first.touch()
            second.touch()
            tags = {
                first: MediaTagOptions(include_resolution=True, resolution="2160p", include_audio=True, audio="EAC3"),
                second: MediaTagOptions(include_resolution=True, resolution="1080p", include_audio=True, audio="AC3"),
            }

            plan = flatten_plan(
                build_movie_plans(
                    folder=folder,
                    movie_name="Example",
                    release_year="2024",
                    extensions={".mkv"},
                    recursive=False,
                    include_sidecars=False,
                    flatten=False,
                    normalize_movie_nfo=False,
                    media_tags=lambda path: tags[path],
                )
            )

            targets = sorted(item.new_path.name for item in plan if item.kind == "movie")
            self.assertEqual(
                targets,
                [
                    "Example (2024) - 1080p AC3.mkv",
                    "Example (2024) - 2160p EAC3.mkv",
                ],
            )

    def test_ffprobe_data_maps_to_media_tags(self) -> None:
        tags = tags_from_ffprobe_data(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "hevc",
                        "height": 2160,
                        "color_transfer": "smpte2084",
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "dts",
                        "tags": {"title": "DTS-HD Master Audio 5.1"},
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "eac3",
                    },
                ]
            }
        )

        self.assertEqual(tags.resolution, "2160p")
        self.assertEqual(tags.hdr, "HDR")
        self.assertEqual(tags.video_codec, "HEVC")
        self.assertEqual(tags.audio, "DTS-HD MA")

    def test_movie_media_tags_are_appended_to_movie_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "John Wick"
            folder.mkdir()
            (folder / "source.mkv").touch()

            plan = flatten_plan(
                build_movie_plans(
                    folder=folder,
                    movie_name="John Wick",
                    release_year="2014",
                    extensions={".mkv"},
                    recursive=False,
                    include_sidecars=False,
                    flatten=False,
                    normalize_movie_nfo=False,
                    media_tags=MediaTagOptions(
                        include_resolution=True,
                        resolution="2160p",
                        include_hdr=True,
                        hdr="HDR",
                        include_video_codec=True,
                        video_codec="HEVC",
                        include_audio=True,
                        audio="DTS-HD MA",
                        include_custom=True,
                        custom="Remote",
                    ),
                )
            )

            video = next(item for item in plan if item.kind == "movie")
            self.assertEqual(video.new_path.name, "John Wick (2014) - 2160p HDR HEVC DTS-HD MA Remote.mkv")

    def test_movie_flatten_uses_untagged_folder_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Old.Release"
            folder.mkdir()
            (folder / "source.mkv").touch()

            plan = flatten_plan(
                build_movie_plans(
                    folder=folder,
                    movie_name="John Wick",
                    release_year="2014",
                    extensions={".mkv"},
                    recursive=False,
                    include_sidecars=False,
                    flatten=True,
                    normalize_movie_nfo=False,
                    media_tags=MediaTagOptions(
                        include_resolution=True,
                        resolution="2160p",
                        include_video_codec=True,
                        video_codec="HEVC",
                        include_audio=True,
                        audio="EAC3",
                    ),
                )
            )

            video = next(item for item in plan if item.kind == "movie")
            self.assertEqual(
                video.new_path.relative_to(root),
                Path("John Wick (2014)") / "John Wick (2014) - 2160p HEVC EAC3.mkv",
            )

    def test_movie_flatten_can_include_media_tags_in_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Old.Release"
            folder.mkdir()
            (folder / "source.mkv").touch()

            plan = flatten_plan(
                build_movie_plans(
                    folder=folder,
                    movie_name="John Wick",
                    release_year="2014",
                    extensions={".mkv"},
                    recursive=False,
                    include_sidecars=False,
                    flatten=True,
                    normalize_movie_nfo=False,
                    media_tags=MediaTagOptions(
                        include_resolution=True,
                        resolution="2160p",
                        include_video_codec=True,
                        video_codec="HEVC",
                        include_audio=True,
                        audio="EAC3",
                    ),
                    media_tags_in_folders=True,
                )
            )

            video = next(item for item in plan if item.kind == "movie")
            self.assertEqual(
                video.new_path.relative_to(root),
                Path("John Wick (2014) - 2160p HEVC EAC3") / "John Wick (2014) - 2160p HEVC EAC3.mkv",
            )

    def test_episode_media_tags_do_not_change_show_or_season_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Example Show" / "Example.Show.S01"
            folder.mkdir(parents=True)
            (folder / "Example.Show.S01E01.mkv").touch()

            plan = flatten_plan(
                build_episode_plans(
                    folder=folder,
                    series_name="Example Show",
                    season=1,
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=False,
                    episode_from_path=True,
                    include_sidecars=False,
                    flatten=False,
                    series_year="2024",
                    rename_show_folder=True,
                    normalize_season_folder=True,
                    normalize_show_nfo=True,
                    media_tags=MediaTagOptions(
                        include_resolution=True,
                        resolution="1080p",
                        include_video_codec=True,
                        video_codec="HEVC",
                        include_audio=True,
                        audio="EAC3",
                    ),
                )
            )

            video = next(item for item in plan if item.kind == "video")
            self.assertEqual(
                video.new_path.relative_to(root),
                Path("Example Show (2024)") / "Season 01" / "Example Show - S01E01 - 1080p HEVC EAC3.mkv",
            )

    def test_episode_flatten_can_include_media_tags_in_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Example.Show.S01"
            folder.mkdir()
            (folder / "Example.Show.S01E01.mkv").touch()

            plan = flatten_plan(
                build_episode_plans(
                    folder=folder,
                    series_name="Example Show",
                    season=1,
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=False,
                    episode_from_path=True,
                    include_sidecars=False,
                    flatten=True,
                    series_year="",
                    rename_show_folder=False,
                    normalize_season_folder=False,
                    normalize_show_nfo=False,
                    media_tags=MediaTagOptions(
                        include_resolution=True,
                        resolution="1080p",
                        include_audio=True,
                        audio="EAC3",
                    ),
                    media_tags_in_folders=True,
                )
            )

            video = next(item for item in plan if item.kind == "video")
            self.assertEqual(
                video.new_path.relative_to(folder),
                Path("Example Show - S01E01 - 1080p EAC3") / "Example Show - S01E01 - 1080p EAC3.mkv",
            )

    def test_movie_duplicate_trickplay_keeps_newest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "A.I. - Kuenstliche Intelligenz (2001)"
            folder.mkdir()
            video = folder / "A.I. - Kuenstliche Intelligenz (2001).mkv"
            video.touch()
            old_trickplay = folder / "old.trickplay"
            old_trickplay.mkdir()
            newest_trickplay = folder / "newer.trickplay"
            newest_trickplay.mkdir()

            plan = flatten_plan(
                build_movie_plans(
                    folder=folder,
                    movie_name="A.I. - Kuenstliche Intelligenz",
                    release_year="2001",
                    extensions={".mkv"},
                    recursive=False,
                    include_sidecars=True,
                    flatten=False,
                    normalize_movie_nfo=True,
                )
            )

            self.assertEqual(validate_plan(plan), [])
            trickplay_items = [item for item in plan if item.kind == "trickplay"]
            delete_items = [item for item in plan if item.kind == "delete"]
            self.assertEqual(len(trickplay_items), 1)
            self.assertEqual(trickplay_items[0].new_path.name, "A.I. - Kuenstliche Intelligenz (2001).trickplay")
            self.assertEqual(len(delete_items), 1)

    def test_duplicate_orphan_episode_nfo_is_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "Blue.Mountain.State.S01"
            episode_dir = folder / "Blue.Mountain.State.S01E10.Release"
            episode_dir.mkdir(parents=True)
            (episode_dir / "Blue.Mountain.State.S01E10.Release.mkv").touch()
            (episode_dir / "Blue.Mountain.State.S01E10.Release.nfo").touch()
            (episode_dir / "tvmaze.nfo").touch()

            plan = flatten_plan(
                build_episode_plans(
                    folder=folder,
                    series_name="Blue Mountain State",
                    season=1,
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=True,
                    episode_from_path=True,
                    include_sidecars=True,
                    flatten=False,
                    series_year="2022",
                    rename_show_folder=True,
                    normalize_season_folder=True,
                    normalize_show_nfo=False,
                )
            )

            self.assertEqual(validate_plan(plan), [])
            self.assertTrue(any(item.kind == "delete" and item.old_path.name == "tvmaze.nfo" for item in plan))

    def test_dropped_release_season_targets_parent_show_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Blue Mountain State" / "Blue.Mountain.State.S01"
            episode_dir = folder / "Blue.Mountain.State.S01E10.Release"
            episode_dir.mkdir(parents=True)
            (episode_dir / "Blue.Mountain.State.S01E10.Release.mkv").touch()

            plan = flatten_plan(
                build_episode_plans(
                    folder=folder,
                    series_name="Blue Mountain State",
                    season=1,
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=True,
                    episode_from_path=True,
                    include_sidecars=True,
                    flatten=False,
                    series_year="2022",
                    rename_show_folder=True,
                    normalize_season_folder=True,
                    normalize_show_nfo=True,
                )
            )

            video = next(item for item in plan if item.kind == "video")
            self.assertEqual(
                video.new_path.relative_to(root),
                Path("Blue Mountain State (2022)") / "Season 01" / "Blue Mountain State - S01E10.mkv",
            )

    def test_multi_part_episode_uses_episode_range_in_target_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Example.Show.S01"
            folder.mkdir()
            (folder / "Example.Show.S01E01-E02.Release.mkv").touch()

            plan = flatten_plan(
                build_episode_plans(
                    folder=folder,
                    series_name="Example Show",
                    season=1,
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=False,
                    episode_from_path=True,
                    include_sidecars=False,
                    flatten=False,
                    series_year="2024",
                    rename_show_folder=True,
                    normalize_season_folder=True,
                    normalize_show_nfo=True,
                )
            )

            video = next(item for item in plan if item.kind == "video")
            self.assertEqual(video.new_path.name, "Example Show - S01E01-E02.mkv")

    def test_letter_suffixed_episode_parts_keep_unique_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Family.Guy.S06"
            folder.mkdir()
            (folder / "KjVxl5B__Family.Guy.S06E01a.German.AC3.DL.1080p.WebRip.x265-FuN.mkv").touch()
            (folder / "KjVxl5B__Family.Guy.S06E01b.German.AC3.DL.1080p.WebRip.x265-FuN.mkv").touch()

            plan = flatten_plan(
                build_episode_plans(
                    folder=folder,
                    series_name="Family Guy",
                    season=6,
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=False,
                    episode_from_path=True,
                    include_sidecars=False,
                    flatten=False,
                    series_year="1999",
                    rename_show_folder=True,
                    normalize_season_folder=True,
                    normalize_show_nfo=True,
                )
            )

            self.assertEqual(validate_plan(plan), [])
            targets = [item.new_path.name for item in plan if item.kind == "video"]
            self.assertEqual(
                targets,
                [
                    "Family Guy - S06E01 Part 1.mkv",
                    "Family Guy - S06E01 Part 2.mkv",
                ],
            )

    def test_common_part_suffix_spellings_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Example.Show.S01"
            folder.mkdir()
            (folder / "Example.Show.S01E01-part1.Release.mkv").touch()
            (folder / "Example.Show.S01E02A.Release.mkv").touch()
            (folder / "Example.Show.S01E03-Teil1.Release.mkv").touch()

            plan = flatten_plan(
                build_episode_plans(
                    folder=folder,
                    series_name="Example Show",
                    season=1,
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=False,
                    episode_from_path=True,
                    include_sidecars=False,
                    flatten=False,
                    series_year="2024",
                    rename_show_folder=True,
                    normalize_season_folder=True,
                    normalize_show_nfo=True,
                )
            )

            self.assertEqual(validate_plan(plan), [])
            targets = sorted(item.new_path.name for item in plan if item.kind == "video")
            self.assertEqual(
                targets,
                [
                    "Example Show - S01E01 Part 1.mkv",
                    "Example Show - S01E02 Part 1.mkv",
                    "Example Show - S01E03 Part 1.mkv",
                ],
            )

    def test_conflict_group_prefers_multi_part_episode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Example.Show.S01"
            folder.mkdir()
            (folder / "Example.Show.S01E01-E02.Release.mkv").touch()
            (folder / "FIX_Example.Show.S01E01-E02.Release.mkv").touch()

            episode_plans = build_episode_plans(
                folder=folder,
                series_name="Example Show",
                season=1,
                start_episode=1,
                extensions={".mkv"},
                recursive=False,
                episode_from_path=True,
                include_sidecars=False,
                flatten=False,
                series_year="2024",
                rename_show_folder=True,
                normalize_season_folder=True,
                normalize_show_nfo=True,
            )

            groups = build_conflict_groups(episode_plans)
            self.assertEqual(len(groups), 1)
            preferred = next(candidate for candidate in groups[0].candidates if candidate.is_preferred)
            self.assertNotIn("FIX_", preferred.label)

    def test_season_metadata_moves_to_season_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            show_root = root / "Blue Mountain State"
            folder = show_root / "Blue.Mountain.State.S01"
            episode_dir = folder / "Blue.Mountain.State.S01E10.Release"
            episode_dir.mkdir(parents=True)
            (show_root / "tvshow.nfo").touch()
            (show_root / "poster.jpg").touch()
            (folder / "season.nfo").touch()
            (folder / "folder.jpg").touch()
            (episode_dir / "Blue.Mountain.State.S01E10.Release.mkv").touch()

            plan = flatten_plan(
                build_episode_plans(
                    folder=folder,
                    series_name="Blue Mountain State",
                    season=1,
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=True,
                    episode_from_path=True,
                    include_sidecars=True,
                    flatten=False,
                    series_year="2022",
                    rename_show_folder=True,
                    normalize_season_folder=True,
                    normalize_show_nfo=True,
                )
            )

            self.assertEqual(validate_plan(plan), [])
            self.assertTrue(any(item.kind == "show-nfo" and item.new_path.name == "tvshow.nfo" for item in plan))
            self.assertTrue(any(item.kind == "season-nfo" and item.new_path.name == "season.nfo" for item in plan))
            self.assertTrue(any(item.kind == "season-image" and item.new_path.name == "folder.jpg" for item in plan))

    def test_multi_season_show_root_builds_each_season(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            show_root = root / "Example Show"
            s01 = show_root / "Example.Show.S01" / "Example.Show.S01E01.Release"
            s02 = show_root / "Example.Show.S02" / "Example.Show.S02E03.Release"
            s01.mkdir(parents=True)
            s02.mkdir(parents=True)
            (show_root / "tvshow.nfo").touch()
            (show_root / "poster.jpg").touch()
            (s01.parent / "season.nfo").touch()
            (s02.parent / "season.nfo").touch()
            (s01 / "Example.Show.S01E01.Release.mkv").touch()
            (s02 / "Example.Show.S02E03.Release.mkv").touch()

            plan = flatten_plan(
                build_multi_season_episode_plans(
                    folder=show_root,
                    series_name="Example Show",
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=True,
                    include_sidecars=True,
                    flatten=False,
                    series_year="2024",
                    rename_show_folder=True,
                    normalize_season_folder=True,
                    normalize_show_nfo=True,
                )
            )

            self.assertEqual(validate_plan(plan), [])
            targets = {item.new_path.relative_to(root) for item in plan if item.kind == "video"}
            self.assertEqual(
                targets,
                {
                    Path("Example Show (2024)") / "Season 01" / "Example Show - S01E01.mkv",
                    Path("Example Show (2024)") / "Season 02" / "Example Show - S02E03.mkv",
                },
            )
            self.assertEqual(sum(1 for item in plan if item.kind == "show-nfo"), 1)
            self.assertEqual(sum(1 for item in plan if item.kind == "season-nfo"), 2)

    def test_stale_source_dir_detected_when_targets_leave_old_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            show_root = root / "Example.Show"
            season_dir = show_root / "Example.Show.S01"
            episode_dir = season_dir / "Example.Show.S01E01.Release"
            episode_dir.mkdir(parents=True)
            (episode_dir / "Example.Show.S01E01.Release.mkv").touch()

            plan = flatten_plan(
                build_multi_season_episode_plans(
                    folder=show_root,
                    series_name="Example Show",
                    start_episode=1,
                    extensions={".mkv"},
                    recursive=True,
                    include_sidecars=True,
                    flatten=False,
                    series_year="2024",
                    rename_show_folder=True,
                    normalize_season_folder=True,
                    normalize_show_nfo=True,
                )
            )

            self.assertEqual(find_stale_source_dirs(show_root, plan), [show_root.resolve()])


class DetectionTests(unittest.TestCase):
    def test_parse_movie_folder(self) -> None:
        self.assertEqual(parse_movie_folder_name("A.I. - Kuenstliche Intelligenz (2001)"), ("A.I. - Kuenstliche Intelligenz", "2001"))

    def test_parse_show_season_folder(self) -> None:
        title, season = parse_show_folder_name(Path("/Shows/Blue Mountain State/Blue.Mountain.State.S01"))
        self.assertEqual(title, "Blue Mountain State")
        self.assertEqual(season, 1)

    def test_parse_show_specials_folder(self) -> None:
        title, season = parse_show_folder_name(Path("/Shows/Example Show/Season 00"))
        self.assertEqual(title, "Example Show")
        self.assertEqual(season, 0)


if __name__ == "__main__":
    unittest.main()
