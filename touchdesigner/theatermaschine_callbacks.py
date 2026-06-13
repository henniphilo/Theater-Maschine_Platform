# Copy into a Callbacks DAT linked to your OSC In DAT (port 7000).
# Textport (Alt+T) must show lines when OSC arrives.

CLIP_MAP = {
    "kuh": "kuh.mov",
    "fuchs": "fuchs.mov",
    "ente": "Ente.mov",
    "bar_avatar": "Bär Avatar.mp4",
    "fuchs_avatar": "Fuchs Avatar.mp4",
    "hund_avatar": "Hund Avatar.mp4",
    "esel_lauft_27-05": "Esel läuft 27-05.mp4",
    "lowe_test": "Löwe Test.mp4",
    "gehirn_test": "Gehirn Test.mp4",
    "schmetterlinge": "Schmetterlinge.mp4",
    "insekten": "Insekten.mp4",
    "mehlwurmer": "Mehlwürmer.mp4",
}

# Path to media/video on your machine (adjust if needed):
MEDIA_VIDEO_DIR = "/Users/multimediapc146/Documents/Code/Theatermaschine/media/video"


def onReceiveOSC(dat, rowIndex, message, bytes, time, address, args, peer):
    print(f"[TM] OSC {address} {args} from {peer}")
    if address == "/theatermaschine/ping":
        return
    if address == "/visual/play_clip" and len(args) >= 1:
        clip_id = str(args[0])
        opacity = float(args[1]) if len(args) > 1 else 0.8
        fade = float(args[2]) if len(args) > 2 else 4.0
        filename = CLIP_MAP.get(clip_id)
        if not filename:
            print(f"[TM] unknown clip_id: {clip_id}")
            return
        path = f"{MEDIA_VIDEO_DIR}/{filename}"
        router = op("media_router")  # noqa: F821 — TouchDesigner runtime
        router.par.Clipid = clip_id
        router.par.File = path
        op("level_top").par.opacity = opacity  # noqa: F821
        op("cross_top").par.fade = fade  # noqa: F821
        print(f"[TM] play_clip {clip_id} -> {path}")
    return
