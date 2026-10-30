from fplcore.settings import split_origins


def test_split_origins_trims_blanks_and_slashes() -> None:
    assert split_origins(" http://localhost:3000, https://fplbud.vercel.app/ , ") == [
        "http://localhost:3000",
        "https://fplbud.vercel.app",
    ]
