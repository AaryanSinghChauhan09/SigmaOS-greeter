"""Display manager / greeter configuration for SigmaOS-greeter.

Principles: pure plan layer (no greeter or compositor process is launched by
tests), fail-fast on malformed passwd input, secure defaults (system accounts
hidden, accessibility options range-checked), deterministic ordering.
"""
import argparse, json, os, re, sys

ENGINE = {
    "name": "sigma-greeter",
    "summary": "User lists, themes, accessibility and launch plans",
    "language": "python",
    "verbs": ["users", "theme", "a11y", "launch-plan"],
    "principles": ["Secure Defaults", "Fail-Fast", "Pure Plan / Thin Execute",
                   "KISS", "Deterministic Testing"],
}

cli_doc = """\
$ sigma-greeter users passwd.txt --min-uid 1000
$ sigma-greeter theme sigma-dark
$ sigma-greeter a11y a11y.json
$ sigma-greeter launch-plan --theme sigma-dark --session wayland
"""

THEMES = ("sigma-dark", "sigma-light", "sigma-plain")
_SESSION_TYPES = ("wayland", "tty")
_NOLOGIN = ("/usr/sbin/nologin", "/bin/false", "/sbin/nologin")


class GreeterError(Exception):
    pass


def parse_passwd(text, min_uid=1000, include_nologin=False):
    """Pure: parse passwd-style text -> sorted login-able user dicts."""
    users, names = [], set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(":")
        if len(fields) != 7:
            raise GreeterError(f"line {lineno}: expected 7 fields, got {len(fields)}")
        name, _pw, uid_s, _gid, gecos, home, shell = fields
        if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", name):
            raise GreeterError(f"line {lineno}: bad user name: {name!r}")
        try:
            uid = int(uid_s)
        except ValueError:
            raise GreeterError(f"line {lineno}: bad uid: {uid_s!r}") from None
        if uid < min_uid:
            continue                      # system account: hidden
        if shell in _NOLOGIN and not include_nologin:
            continue                      # no shell: not login-able
        if name in names:
            raise GreeterError(f"duplicate user: {name}")
        names.add(name)
        users.append({"name": name, "uid": uid, "gecos": gecos,
                      "home": home, "shell": shell})
    return sorted(users, key=lambda u: (u["uid"], u["name"]))


def theme_config(name):
    """Pure: validated greeter theme configuration."""
    if name not in THEMES:
        raise GreeterError(f"unknown theme: {name!r} (one of {THEMES})")
    return {"name": name, "font": "Inter 13", "icon": "avatar-symbolic",
            "blur": name != "sigma-plain"}


def a11y(settings):
    """Pure: validate accessibility settings against safe ranges."""
    font_scale = settings.get("font_scale", 1.0)
    if not isinstance(font_scale, (int, float)) or isinstance(font_scale, bool) \
            or not (1.0 <= float(font_scale) <= 3.0):
        raise GreeterError(f"font_scale must be 1.0..3.0, got {font_scale!r}")
    timeout = settings.get("user_timeout", 0)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not (0 <= timeout <= 120):
        raise GreeterError(f"user_timeout must be 0..120, got {timeout!r}")
    out = {"font_scale": float(font_scale), "user_timeout": timeout}
    for flag in ("high_contrast", "screen_reader", "keyboard_navigation",
                 "large_cursor"):
        value = settings.get(flag, False)
        if not isinstance(value, bool):
            raise GreeterError(f"{flag} must be a boolean, got {value!r}")
        out[flag] = value
    if out["screen_reader"] and not out["keyboard_navigation"]:
        raise GreeterError("screen_reader requires keyboard_navigation")
    return dict(sorted(out.items()))


def launch_plan(theme="sigma-dark", session_type="wayland", user=None):
    """Pure: ordered launch steps (compositor -> greeter -> user session)."""
    theme_config(theme)
    if session_type not in _SESSION_TYPES:
        raise GreeterError(f"bad session type: {session_type!r}")
    if user is not None and not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user):
        raise GreeterError(f"bad user name: {user!r}")
    steps = [
        {"order": 1, "step": "compositor",
         "cmd": f"sigma-desktop --session {session_type}"},
        {"order": 2, "step": "greeter",
         "cmd": f"sigma-greeter --theme {theme}",
         "after": "compositor"},
        {"order": 3, "step": "session",
         "cmd": f"sigma-session start --user {user or '{user}'}",
         "after": "greeter-auth"},
    ]
    return steps


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("users", help="login-able users from a passwd file")
    u.add_argument("passwd", help="passwd-format file (tests use a temp copy)")
    u.add_argument("--min-uid", type=int, default=1000)
    u.add_argument("--include-nologin", action="store_true")
    t = sub.add_parser("theme", help="greeter theme config")
    t.add_argument("name", choices=THEMES)
    a = sub.add_parser("a11y", help="validate accessibility settings")
    a.add_argument("settings", help="JSON object of a11y settings")
    l = sub.add_parser("launch-plan", help="ordered launch steps")
    l.add_argument("--theme", default="sigma-dark", choices=THEMES)
    l.add_argument("--session", default="wayland", choices=_SESSION_TYPES,
                   dest="session_type")
    l.add_argument("--user", default=None)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "theme":
            cfg = theme_config(args.name)
            print(f"{cfg['name']}: font={cfg['font']} icon={cfg['icon']} "
                  f"blur={cfg['blur']}")
            return 0
        if args.cmd == "a11y":
            with open(args.settings, "r", encoding="utf-8") as fh:
                cfg = a11y(json.load(fh))
            for k, v in cfg.items():
                print(f"{k}={v}")
            return 0
        if args.cmd == "users":
            with open(args.passwd, "r", encoding="utf-8") as fh:
                text = fh.read()
            for u in parse_passwd(text, min_uid=args.min_uid,
                                  include_nologin=args.include_nologin):
                print(f"{u['name']} (uid={u['uid']}) {u['gecos']} -> {u['home']}")
            return 0
        for step in launch_plan(args.theme, args.session_type, args.user):
            print(f"{step['order']}. {step['step']}: {step['cmd']}")
        return 0
    except (GreeterError, OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    import tempfile
    passwd = "\n".join([
        "root:x:0:0:root:/root:/bin/bash",
        "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin",
        "alice:x:1000:1000:Alice A:/home/alice:/bin/bash",
        "bob:x:1001:1001:Bob B:/home/bob:/bin/zsh",
        "svc:x:999:999:Service:/var/lib/svc:/usr/sbin/nologin",
        "carol:x:1002:1002:Carol C:/home/carol:/bin/bash",
        "",
    ])
    users = parse_passwd(passwd)
    assert [u["name"] for u in users] == ["alice", "bob", "carol"]
    assert [u["uid"] for u in users] == [1000, 1001, 1002]  # sorted, hidden systems
    assert users[0]["home"] == "/home/alice"
    # min_uid / nologin toggles
    assert len(parse_passwd(passwd, min_uid=0)) == 4        # alice,bob,carol + root
    assert len(parse_passwd(passwd, min_uid=0, include_nologin=True)) == 6
    # malformed input is fail-fast
    for bad_text in (
        "alice:x:1000:bad:only:fields",                 # wrong field count
        "Alice:x:1000:1000:A:/home/A:/bin/bash",        # bad name
        "alice:x:notanumber:1:A:/home/a:/bin/bash",     # bad uid
        passwd + "dave:x:1003:1003:D:/home/dave:/bin/bash\n"
                 "dave:x:1004:1004:D:/home/dave2:/bin/bash",  # duplicate
    ):
        try:
            parse_passwd(bad_text)
        except GreeterError:
            pass
        else:
            raise AssertionError(f"not rejected: {bad_text[:40]!r}")
    # theme
    cfg = theme_config("sigma-dark")
    assert cfg["name"] == "sigma-dark" and cfg["blur"] is True
    assert theme_config("sigma-plain")["blur"] is False
    try:
        theme_config("neon-chaos")
    except GreeterError:
        pass
    else:
        raise AssertionError("unknown theme not rejected")
    # a11y
    good = a11y({"font_scale": 1.5, "high_contrast": True,
                 "keyboard_navigation": True, "screen_reader": True})
    assert good["font_scale"] == 1.5 and good["screen_reader"] is True
    assert list(good) == sorted(good)
    for bad_call in (
        lambda: a11y({"font_scale": 0.5}),
        lambda: a11y({"font_scale": 4.0}),
        lambda: a11y({"user_timeout": -1}),
        lambda: a11y({"high_contrast": "yes"}),
        lambda: a11y({"screen_reader": True}),          # without keyboard nav
    ):
        try:
            bad_call()
        except GreeterError:
            pass
        else:
            raise AssertionError("expected GreeterError (a11y)")
    # launch plan ordering
    plan = launch_plan("sigma-dark", "wayland", user="alice")
    assert [s["step"] for s in plan] == ["compositor", "greeter", "session"]
    assert [s["order"] for s in plan] == [1, 2, 3]
    assert plan[0]["cmd"].endswith("--session wayland")
    assert plan[2]["cmd"].endswith("--user alice")
    for bad_call in (
        lambda: launch_plan("sigma-dark", "x11"),
        lambda: launch_plan("sigma-dark", "wayland", user="Bad User"),
    ):
        try:
            bad_call()
        except GreeterError:
            pass
        else:
            raise AssertionError("expected GreeterError (launch)")
    # CLI smoke through main()
    with tempfile.TemporaryDirectory() as d:
        pw = os.path.join(d, "passwd")
        with open(pw, "w", encoding="utf-8") as fh:
            fh.write(passwd)
        ap = os.path.join(d, "a11y.json")
        with open(ap, "w", encoding="utf-8") as fh:
            json.dump({"font_scale": 1.25, "keyboard_navigation": True}, fh)
        assert main(["users", pw]) == 0
        assert main(["theme", "sigma-light"]) == 0
        assert main(["a11y", ap]) == 0
        assert main(["launch-plan", "--theme", "sigma-dark", "--user", "alice"]) == 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
