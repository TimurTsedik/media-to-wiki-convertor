from media_to_wiki_convertor.cli import build_parser


def test_import_transcript_parser_accepts_required_arguments() -> None:
    args = build_parser().parse_args(
        [
            "import-transcript",
            "--video-id",
            "abc123",
            "--file",
            "transcript.txt",
            "--force",
        ]
    )

    assert args.command == "import-transcript"
    assert args.video_id == "abc123"
    assert str(args.file) == "transcript.txt"
    assert args.force is True
