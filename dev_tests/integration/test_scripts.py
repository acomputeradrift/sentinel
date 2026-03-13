import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTRACT = ROOT / "src" / "sentinel" / "extraction" / "extract_project_data.py"
GENERATE = ROOT / "src" / "sentinel" / "generation" / "generate_html.py"


def orientation_ui(font_size: int, top: int, left: int, height: int, width: int, *, p_visible: bool = True, l_visible: bool = False, l_top: int | None = None, l_left: int | None = None, l_height: int | None = None, l_width: int | None = None) -> dict:
    return {
        "fontSize": font_size,
        "orientations": {
            "portrait": {
                "visible": p_visible,
                "coordinates": {"top": top, "left": left, "height": height, "width": width},
            },
            "landscape": {
                "visible": l_visible,
                "coordinates": {
                    "top": top if l_top is None else l_top,
                    "left": left if l_left is None else l_left,
                    "height": height if l_height is None else l_height,
                    "width": width if l_width is None else l_width,
                },
            },
        },
    }


def sample_app_ui() -> dict:
    return {
        "appUiStructureVersion": "1.0.0",
        "layout": {
            "appCanvas": {"mode": "browser-viewport"},
            "appUIControls": {"top": 52, "bottom": 32, "left": 300, "right": 300},
            "rtiCanvas": {"deriveFromAppCanvas": True},
            "rtiDeviceCanvas": {
                "fitMode": "contain",
                "allowScaleAboveOne": True,
                "maxScale": 10,
                "minScale": 0.25,
                "centerWithinRtiCanvas": True,
            },
        },
        "uiHierarchy": {
            "appCanvas": ["appUIControls", "rtiCanvas"],
            "rtiCanvas": ["rtiDeviceCanvas"],
            "rtiDeviceUI": ["projectButtons", "projectViewports"],
            "appUIControls": ["header", "appNavigation", "viewportNavigation"],
            "rtiDeviceCanvas": ["rtiDeviceUI"],
        },
        "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
        "appNavigation": {
            "enabled": True,
            "placement": "canvas-adjacent",
            "showPageControls": True,
            "pageLinks": {
                "enabled": True,
                "showLinkAffordanceOnHover": True,
                "iconPlacement": "right-center-inside-button",
                "iconStyle": "inline-svg",
                "iconSize": 16,
                "iconPaddingRight": 8,
                "hoverActivationArea": {"width": 28, "fullButtonHeight": True},
            },
        },
        "zoomControls": {
            "enabled": True,
            "placement": {"anchor": "left-control-space", "alignTopToRtiCanvas": True, "centerHorizontallyInControlSpace": True},
            "buttons": {"decrease": "-", "reset": "100%", "increase": "+"},
            "zoom": {"defaultPercent": 100, "maxPercent": 200, "stepPercent": 10},
            "scrollbars": {"showOnHover": True, "thickness": 10},
        },
        "viewportNavigation": {
            "enabled": False,
            "placement": {"previous": "canvas-left-center", "next": "canvas-right-center", "frameIndicator": "canvas-bottom-center", "edgeOffset": 36},
            "indicatorStyle": "dots",
            "labels": {"previous": "Prev", "next": "Next"},
            "behavior": {"wrapFrames": False},
        },
        "testingPopup": {
            "enabled": True,
            "titleTemplate": "{category} Test - {identity}",
            "includeButtonTypeInTitle": True,
            "showIdentity": True,
            "variableLabelTemplate": "Variable - {variableType}",
            "targetGroupStyle": "single-group-per-target",
            "showOnlyTrueTargets": True,
            "failNoteRequiredOnFail": True,
        },
        "buttonPresentation": {"useProjectFontSize": True, "fallbackFontSize": 10, "preserveRtiCoordinates": True, "scaleRtiDerivedFontSizes": True},
        "viewportPresentation": {"showViewportContainer": True, "renderViewportButtonsByDefault": False, "initialFrameStrategy": "defaultFrameId"},
        "state": {"persistTestResults": True, "persistViewportFrameSelection": True},
    }


def create_test_apex(path: Path) -> None:
    con = sqlite3.connect(path)
    cur = con.cursor()

    cur.executescript(
        """
        create table Devices (DeviceId integer primary key, RoomId integer, DisplayOrder integer, ControlType integer, Name text, Manufacturer text, Type text, Model text, Comment text, HasCompositeController integer, SourceType integer, DisplayName text);
        create table RTIDeviceData (RTIAddress integer primary key, DeviceId integer, CloneRTIAddress integer, SupportedOrientations integer, ScreenPortraitWidth integer, ScreenPortraitHeight integer, ScreenLandscapeWidth integer, ScreenLandscapeHeight integer);
        create table RTIDevicePageData (PageId integer primary key, SourceDeviceId integer, PageNameId integer, RTIAddress integer, PageOrder integer);
        create table PageNames (PageNameId integer primary key, PageName text);
        create table Layers (LayerId integer primary key, PageId integer, SourceId integer, SharedLayerId integer, LayerOrder integer, IsVisible integer, VisibilityVariable text, IsLocked integer, ViewPortButtonId integer, RoomId integer);
        create table RTIDeviceButtonData (ButtonId integer primary key, SharedLayerId integer, ButtonOrder integer, ButtonTagId integer, FrameNumber integer, ButtonTop integer, ButtonLeft integer, ButtonHeight integer, ButtonWidth integer, Text text, TextSize integer, ButtonStyle integer, ButtonTopAlt integer, ButtonLeftAlt integer, ButtonHeightAlt integer, ButtonWidthAlt integer, VisibleOrientations integer, ViewPortVerticalScroll integer);
        create table ButtonTagNames (ButtonTagId integer primary key, ButtonTagName text);
        create table Variables (VariableId integer primary key, RoomId integer, DeviceId integer, ButtonTagId integer, ButtonText text, ObjectData text, ReversedData text, InactiveData text, VisibleData text);
        create table ButtonTextTags (ButtonTextTagId integer primary key, ButtonId integer, ButtonTagId integer);
        create table Rooms (RoomId integer primary key, Name text, HomePageId integer, RoomOrder integer);
        create table Macros (MacroId integer primary key, SystemMacroId integer, RoomId integer, DeviceId integer, ButtonTagId integer, OutputType integer);
        create table MacroSteps (MacroStepId integer primary key, MacroId integer, StepIndex integer, Type integer, Level integer, InElseSection integer);
        create table PageLinks (PageLinkId integer primary key, DeviceId integer, ButtonTagId integer, LinkType integer, PageId integer);
        create table Events (EventId integer primary key, EventType integer, MacroId integer, Description text, Enabled integer, DriverId integer, DriverExtraString text);
        create table DriverData (DriverDeviceId integer primary key, DeviceId integer, Enabled integer, DriverId text, SystemFunctions text);
        """
    )

    cur.execute("insert into Devices values (1,0,1,5,'IST-5','','','','',0,0,'IST-5 (Global)')")
    cur.execute("insert into RTIDeviceData values (1,1,0,1,480,854,0,0)")
    cur.execute("insert into PageNames values (10,'Lights')")
    cur.execute("insert into PageNames values (11,'Home')")
    cur.execute("insert into Rooms values (0,'Global',0,0)")
    cur.execute("insert into RTIDevicePageData values (100,1,10,1,0)")
    cur.execute("insert into RTIDevicePageData values (101,1,11,1,1)")
    cur.execute("insert into Layers values (200,100,1,300,0,1,'',0,null,0)")
    cur.execute("insert into Layers values (201,101,1,301,0,1,'',0,null,0)")

    cur.execute("insert into ButtonTagNames values (114,'LIGHTS - Load 2 Level')")
    cur.execute("insert into ButtonTagNames values (129,'LIGHTS - Load 2 TOGGLE')")

    cur.execute("insert into RTIDeviceButtonData values (246,300,0,114,0,140,30,46,284,'',10,9,20,320,46,284,2,0)")
    cur.execute("insert into RTIDeviceButtonData values (247,300,1,129,0,140,334,46,76,'',10,7,20,620,46,76,2,0)")

    cur.execute("insert into Variables values (1,0,-1,114,'$%VARIABLE!x@DDL002%$','token@DDL002',null,null,null)")
    cur.execute("insert into Variables values (2,0,-1,129,null,'token@DDS002',null,null,null)")

    cur.execute("insert into Macros values (362,362,0,-1,129,0)")
    cur.execute("insert into MacroSteps values (1,362,0,1,0,0)")
    cur.execute("insert into Events values (1,1,362,'Sense Test',1,null,null)")
    cur.execute("insert into Events values (2,5,362,'Driver Test',1,99,'fallback')")
    cur.execute("insert into DriverData values (99,1,1,'Driver Name','SwitchCmd:Switch;DimmerCmd:SetLevel')")
    cur.execute("insert into PageLinks values (1,1,129,0,101)")

    con.commit()
    con.close()


class ScriptContractsTest(unittest.TestCase):
    def test_extract_creates_project_data_json(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            apex = td_path / "sample.apex"
            schema = td_path / "apex_project_structure.json"
            schema.write_text("{}", encoding="utf-8")
            create_test_apex(apex)

            run = subprocess.run(
                [sys.executable, str(EXTRACT), "--apex", str(apex), "--project-structure", str(schema), "--out-dir", str(td_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            data = json.loads((td_path / "sample_project_data.json").read_text(encoding="utf-8"))
            slider = data["devices"][0]["userFacing"]["pages"][0]["buttonCategories"]["screenButtons"][0]
            toggle = data["devices"][0]["userFacing"]["pages"][0]["buttonCategories"]["screenButtons"][1]
            self.assertTrue(slider["buttonUI"]["orientations"]["portrait"]["visible"])
            self.assertFalse(slider["buttonUI"]["orientations"]["landscape"]["visible"])
            self.assertEqual(slider["buttonUI"]["orientations"]["portrait"]["coordinates"]["left"], 30)
            self.assertEqual(slider["buttonUI"]["orientations"]["landscape"]["coordinates"]["left"], 320)
            self.assertTrue(slider["testTargets"]["variables"]["Value"])
            self.assertFalse(slider["testTargets"]["variables"]["State"])
            self.assertTrue(slider["testTargets"]["variables"]["Command"])
            self.assertEqual(slider["testTargets"]["pageLink"], {"enabled": False, "targetPageId": None})
            self.assertEqual(toggle["testTargets"]["pageLink"], {"enabled": True, "targetPageId": 101})

    def test_generate_writes_html(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data = {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "IST-5 (Global)",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                                "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                            },
                            "pages": [
                                {
                                    "pageName": "Lights",
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [
                                            {
                                                "buttonIdentity": {"buttonTagName": "X", "text": "Btn", "buttonType": "Slider"},
                                                "buttonUI": orientation_ui(10, 10, 10, 40, 100),
                                                "testTargets": {
                                                    "text": True,
                                                    "macro": False,
                                                    "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": True, "State": False, "Command": True},
                                                    "pageLink": {"enabled": False, "targetPageId": None},
                                                },
                                            }
                                        ],
                                        "hardButtons": [],
                                    },
                                    "viewports": [],
                                }
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 100, "pageName": "Lights"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            html = (td_path / "sample_project_data__device-0-ist-5-global.html").read_text(encoding="utf-8")
            self.assertIn("IST-5 (Global) - Lights", html)
            self.assertIn("Variable - Value", html)
            self.assertIn(">Btn</button>", html)
            self.assertIn("const APP_UI_CONTROLS=", html)
            self.assertIn("const RTI_DEVICE_LAYOUT=", html)
            self.assertIn("const VIEWPORT_NAV=", html)
            self.assertIn("const ZOOM_CONTROLS=", html)
            self.assertIn("const widthScale=rtiCanvasWidth/SOURCE_DEVICE_SIZE.width;", html)
            self.assertIn("const heightScale=rtiCanvasHeight/SOURCE_DEVICE_SIZE.height;", html)
            self.assertIn("let scale=Math.min(widthScale,heightScale);", html)
            self.assertIn("id='rtiCanvas'", html)
            self.assertIn("id='rtiDeviceCanvas'", html)
            self.assertIn("leftControls.style.width", html)
            self.assertIn("rightControls.style.width", html)
            self.assertIn("const navEdgeOffset=Number(VIEWPORT_NAV.placement?.edgeOffset||36);", html)
            self.assertIn("let viewportLeft=controls.left+currentDeviceLeft-rtiCanvas.scrollLeft;", html)
            self.assertIn("let viewportTop=controls.top+currentDeviceTop-rtiCanvas.scrollTop;", html)
            self.assertIn("const firstViewport=pageEl ? pageEl.querySelector('.vp-box') : null;", html)
            self.assertIn("viewportLeft=controls.left+currentDeviceLeft+rtiCanvas.clientLeft+((Number(firstViewport.dataset.left||0)*totalScale)-rtiCanvas.scrollLeft);", html)
            self.assertIn("viewportTop=controls.top+currentDeviceTop+rtiCanvas.clientTop+((Number(firstViewport.dataset.top||0)*totalScale)-rtiCanvas.scrollTop);", html)
            self.assertIn("viewportRight=viewportLeft+(Number(firstViewport.dataset.width||0)*totalScale);", html)
            self.assertIn("viewportBottom=viewportTop+(Number(firstViewport.dataset.height||0)*totalScale);", html)
            self.assertIn("const leftArrowLeft=Math.max(viewportLeft-navEdgeOffset-44,0);", html)
            self.assertIn("const rightArrowLeft=Math.max(viewportRight+navEdgeOffset,0);", html)
            self.assertIn("const arrowTop=Math.max(viewportTop+(((viewportBottom-viewportTop)-44)/2),0);", html)
            self.assertIn(".app-ui-controls{position:absolute;box-sizing:border-box;z-index:20;}", html)
            self.assertIn(".vp-nav{width:44px;height:44px", html)
            self.assertIn("id='zoomControls'", html)
            self.assertIn("class='zoom-btn zoom-dec'", html)
            self.assertIn("class='zoom-btn zoom-reset'", html)
            self.assertIn("class='zoom-btn zoom-inc'", html)
            self.assertIn("<div class='zoom-controls' id='zoomControls'>", html)
            self.assertIn("const ZOOM_DEFAULT=100;", html)
            self.assertIn("const ZOOM_MAX=200;", html)
            self.assertIn("const ZOOM_STEP=10;", html)
            self.assertIn("let currentViewportIndexes=VP_FRAMES.map(()=>0);", html)
            self.assertIn("function applyViewportState()", html)
            self.assertIn("if (!el.classList.contains('vp-btn')) {", html)
            self.assertIn("applyViewportState();", html)
            self.assertIn("id='rtiContent'", html)
            self.assertIn("rtiCanvas.classList.toggle('scroll-hover'", html)
            self.assertIn("scrollbar-gutter:stable overlay;", html)
            self.assertIn("rtiCanvasEl.addEventListener('scroll', applyRtiLayout, {passive:true});", html)

    def test_generate_writes_single_device_file_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data = {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "IST-5 (Global)",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                                "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                            },
                            "pages": [
                                {"pageName": "Home", "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []}, "viewports": []},
                                {"pageName": "Lights", "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []}, "viewports": []},
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 101, "pageName": "Home"}, {"pageId": 100, "pageName": "Lights"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)
            self.assertTrue((td_path / "sample_project_data__device-0-ist-5-global.html").exists())
            self.assertFalse((td_path / "sample_project_data__page-0-home.html").exists())
            self.assertFalse((td_path / "sample_project_data__page-1-lights.html").exists())

    def test_generate_defaults_output_to_project_data_directory(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data = {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "IST-5 (Global)",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                                "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                            },
                            "pages": [
                                {"pageName": "Home", "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []}, "viewports": []}
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 101, "pageName": "Home"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)
            self.assertTrue((td_path / "sample_project_data__device-0-ist-5-global.html").exists())

    def test_generate_includes_page_link_overlay_and_target(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data = {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "IST-5 (Global)",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                                "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                            },
                            "pages": [
                                {
                                    "pageName": "Home",
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [
                                            {
                                                "buttonIdentity": {"buttonTagName": "GO - Lights", "text": "Lights", "buttonType": None},
                                                "buttonUI": orientation_ui(10, 20, 20, 40, 120),
                                                "testTargets": {
                                                    "text": True,
                                                    "macro": False,
                                                    "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": False, "Command": False},
                                                    "pageLink": {"enabled": True, "targetPageId": 200},
                                                },
                                            }
                                        ],
                                        "hardButtons": [],
                                    },
                                    "viewports": [],
                                },
                                {
                                    "pageName": "Lights",
                                    "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                    "viewports": [],
                                },
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 100, "pageName": "Home"}, {"pageId": 200, "pageName": "Lights"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)
            html = (td_path / "sample_project_data__device-0-ist-5-global.html").read_text(encoding="utf-8")
            self.assertIn("page-link-hit", html)
            self.assertIn("sample_project_data__device-0-ist-5-global.html", html)
            self.assertIn("data-target-page-index='1'", html)
            self.assertIn("PageLink", html)
            self.assertIn("test-btn", html)

    def test_generate_renders_viewport_default_frame_buttons(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data = {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "IST-5 (Global)",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                                "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                            },
                            "pages": [
                                {
                                    "pageName": "Lights",
                                    "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                    "viewports": [
                                        {
                                            "viewportIdentity": {"viewportButtonId": 2},
                                            "viewportUI": {"navigationMode": "page", "orientations": {"portrait": {"visible": True, "coordinates": {"top": 60, "left": 20, "height": 694, "width": 440}}, "landscape": {"visible": False, "coordinates": {"top": 30, "left": 10, "height": 300, "width": 700}}}},
                                            "frames": [
                                                {
                                                    "frameId": 0,
                                                    "buttonCategories": {
                                                        "screenLabels": [],
                                                        "screenButtons": [
                                                            {
                                                                "buttonIdentity": {"buttonTagName": "LIGHTS - Load 2 TOGGLE", "text": "", "buttonType": "Toggle"},
                                                                "buttonUI": orientation_ui(10, 140, 334, 46, 76),
                                                                "testTargets": {
                                                                    "text": False,
                                                                    "macro": True,
                                                                    "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": False, "State": True, "Command": False},
                                                                    "pageLink": {"enabled": False, "targetPageId": None},
                                                                },
                                                            }
                                                        ],
                                                        "hardButtons": [],
                                                    },
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 100, "pageName": "Lights"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            html = (td_path / "sample_project_data__device-0-ist-5-global.html").read_text(encoding="utf-8")
            self.assertIn("LIGHTS - Load 2 TOGGLE", html)
            self.assertIn("data-left='354'", html)
            self.assertIn("data-top='200'", html)


if __name__ == "__main__":
    unittest.main()
