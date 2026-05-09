import plistlib

from net_alpha.service import plist


def test_render_includes_label():
    xml = plist.render(wrapper_path="/u/.net_alpha/bin/net-alpha-wrap", log_path="/u/.net_alpha/logs/service.log")
    parsed = plistlib.loads(xml)
    assert parsed["Label"] == "com.netalpha.service"


def test_render_program_arguments_points_at_wrapper():
    xml = plist.render(wrapper_path="/u/.net_alpha/bin/net-alpha-wrap", log_path="/u/.net_alpha/logs/service.log")
    parsed = plistlib.loads(xml)
    assert parsed["ProgramArguments"] == ["/u/.net_alpha/bin/net-alpha-wrap"]


def test_render_keepalive_only_on_crash():
    xml = plist.render(wrapper_path="/w", log_path="/l")
    parsed = plistlib.loads(xml)
    assert parsed["KeepAlive"] == {"Crashed": True, "SuccessfulExit": False}


def test_render_run_at_load_true():
    xml = plist.render(wrapper_path="/w", log_path="/l")
    parsed = plistlib.loads(xml)
    assert parsed["RunAtLoad"] is True


def test_render_resource_limits():
    xml = plist.render(wrapper_path="/w", log_path="/l")
    parsed = plistlib.loads(xml)
    assert parsed["SoftResourceLimits"]["NumberOfFiles"] == 512
    # 256 MB
    assert parsed["SoftResourceLimits"]["ResidentSetSize"] == 268_435_456


def test_render_log_paths():
    xml = plist.render(wrapper_path="/w", log_path="/var/log.txt")
    parsed = plistlib.loads(xml)
    assert parsed["StandardOutPath"] == "/var/log.txt"
    assert parsed["StandardErrorPath"] == "/var/log.txt"
