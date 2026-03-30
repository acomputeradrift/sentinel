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


def create_test_apex(
    path: Path,
    *,
    supported_orientations: int = 1,
    portrait_width: int = 480,
    portrait_height: int = 854,
    landscape_width: int = 0,
    landscape_height: int = 0,
    screen_width: int = 480,
    screen_height: int = 854,
) -> None:
    con = sqlite3.connect(path)
    cur = con.cursor()

    cur.executescript(
        """
        create table Devices (DeviceId integer primary key, RoomId integer, DisplayOrder integer, ControlType integer, Name text, Manufacturer text, Type text, Model text, Comment text, HasCompositeController integer, SourceType integer, DisplayName text);
        create table RTIDeviceData (RTIAddress integer primary key, DeviceId integer, CloneRTIAddress integer, SupportedOrientations integer, ScreenPortraitWidth integer, ScreenPortraitHeight integer, ScreenLandscapeWidth integer, ScreenLandscapeHeight integer, ScreenWidth integer, ScreenHeight integer);
        create table RTIDevicePageData (PageId integer primary key, SourceDeviceId integer, PageNameId integer, RTIAddress integer, PageOrder integer);
        create table PagesView (PageId integer primary key, PageName text, RoomId integer);
        create table PageNames (PageNameId integer primary key, PageName text);
        create table Layers (LayerId integer primary key, PageId integer, SourceId integer, SharedLayerId integer, LayerOrder integer, IsVisible integer, VisibilityVariable text, IsLocked integer, ViewPortButtonId integer, RoomId integer);
        create table SharedLayers (SharedLayerId integer primary key, Name text);
        create table RTIDeviceButtonData (ButtonId integer primary key, SharedLayerId integer, ButtonOrder integer, ButtonTagId integer, FrameNumber integer, ButtonTop integer, ButtonLeft integer, ButtonHeight integer, ButtonWidth integer, Text text, TextSize integer, ButtonStyle integer, ButtonTopAlt integer, ButtonLeftAlt integer, ButtonHeightAlt integer, ButtonWidthAlt integer, VisibleOrientations integer, ViewPortVerticalScroll integer);
        create table ButtonTagNames (ButtonTagId integer primary key, ButtonTagName text);
        create table Variables (VariableId integer primary key, RoomId integer, DeviceId integer, ButtonTagId integer, ButtonText text, ObjectData text, ReversedData text, InactiveData text, VisibleData text);
        create table ButtonTextTags (ButtonTextTagId integer primary key, ButtonId integer, ButtonTagId integer);
        create table Rooms (RoomId integer primary key, Name text, HomePageId integer, RoomOrder integer);
        create table ControllerRoomList (ControllerRoomListId integer primary key, RTIAddress integer, RoomId integer, ControllerRoomOrder integer);
        create table Macros (MacroId integer primary key, SystemMacroId integer, RoomId integer, DeviceId integer, ButtonTagId integer, OutputType integer);
        create table MacroSteps (MacroStepId integer primary key, MacroId integer, StepIndex integer, Type integer, Level integer, InElseSection integer);
        create table MacroStepsView (MacroStepId integer primary key, MacroId integer, StepIndex integer, Type integer, CommandTagId integer, CommentText text, Name text, Function text, Parameter1 text, Parameter2 text, Parameter3 text, Parameter4 text, DeviceId integer, TargetRTIAddress text, FlagIndex integer, FlagType integer);
        create table MacroSelectRoom (MacroStepId integer primary key, SelectRoomId integer);
        create table MacroSelectSource (MacroStepId integer primary key, SelectSourceId integer, SelectSourceRoomId integer);
        create table MacroRoomOff (MacroStepId integer primary key, RoomOffId integer);
        create table MacroPageLink (MacroStepId integer primary key, Device integer, Page integer, Frame integer, SaveHistory integer, WakeDevice integer, SendToAll integer);
        create table MacroPageLinkView (MacroStepId integer primary key, TargetPageId text, TargetRTIAddress text);
        create table Activities (ActivitiesId integer primary key, RoomId integer, DeviceId integer, ActivityOrder integer, Checked integer, PagelinkMacroId integer);
        create table RoomEvents (RoomEventId integer primary key, RoomId integer, EventType integer, SelectedMacroId integer);
        create table MacroDeviceCommand (MacroStepId integer primary key, VariableId integer, MacroStepType integer, MacroStepIdRef integer);
        create table PageLinks (PageLinkId integer primary key, DeviceId integer, ButtonTagId integer, LinkType integer, PageId integer);
        create table Events (EventId integer primary key, EventType integer, MacroId integer, Description text, Enabled integer, SensePort integer, SenseAction integer, SenseExpanderId integer, PeriodicInterval integer, PeriodicStartTime blob, DailyAstronomical integer, DailyStartTime blob, DailyDayMask integer, StartupType integer, DriverId integer, DriverExtraString text);
        create table DriverData (DriverDeviceId integer primary key, DeviceId integer, Enabled integer, DriverId text, SystemFunctions text, SystemEvents text);
        create table DriverConfig (DriverConfigId integer primary key, DriverDeviceId integer, Name text, Value text);
        create table PortLabels (PortLabelId integer primary key, RTIAddress integer, LabelKey integer, LabelName text);
        create table SenseModeMap (SenseModeId integer primary key, RTIAddress integer, ExpanderId integer, Mask integer);
        """
    )

    cur.execute("insert into Devices values (1,0,1,5,'IST-5','','','','',0,0,'IST-5 (Global)')")
    cur.execute("insert into Devices values (2,23,2,5,'RK3-V','','','','',0,0,'RK3-V (Bed 2)')")
    cur.execute("insert into Devices values (116,23,3,5,'Lights/Home (Bed 2)','','','','',0,2,'Lights/Home (Bed 2)')")
    cur.execute("insert into Devices values (248,23,4,5,'Apple TV 1 (Bed 2)','','','','',0,2,'Apple TV 1 (Bed 2)')")
    cur.execute("insert into Devices values (249,23,5,5,'Samsung TV (Bed 2)','','','','',0,2,'Samsung TV (Bed 2)')")
    cur.execute("insert into Devices values (250,23,5,5,'Sat 1 (Bed 2)','','','','',0,2,'Sat 1 (Bed 2)')")
    cur.execute(
        "insert into RTIDeviceData values (1,1,0,?,?,?,?,?, ?,?)",
        (
            supported_orientations,
            portrait_width,
            portrait_height,
            landscape_width,
            landscape_height,
            screen_width,
            screen_height,
        ),
    )
    cur.execute(
        "insert into RTIDeviceData values (6,2,0,?,?,?,?,?, ?,?)",
        (
            supported_orientations,
            portrait_width,
            portrait_height,
            landscape_width,
            landscape_height,
            screen_width,
            screen_height,
        ),
    )
    cur.execute("insert into PageNames values (10,'Lights')")
    cur.execute("insert into PageNames values (11,'Home')")
    cur.execute("insert into PageNames values (12,'Apple TV 1')")
    cur.execute("insert into PageNames values (13,'Sat TV 1')")
    cur.execute("insert into PageNames values (14,'TV Controls')")
    cur.execute("insert into PagesView values (100,'Lights',0)")
    cur.execute("insert into PagesView values (101,'Home',0)")
    cur.execute("insert into PagesView values (381,'Home',23)")
    cur.execute("insert into PagesView values (397,'Apple TV 1',23)")
    cur.execute("insert into PagesView values (396,'Sat TV 1',23)")
    cur.execute("insert into PagesView values (395,'TV Controls',23)")
    cur.execute("insert into Rooms values (0,'Global',0,0)")
    cur.execute("insert into Rooms values (23,'Bed 2',116,1)")
    cur.execute("insert into ControllerRoomList values (1,1,0,0)")
    cur.execute("insert into ControllerRoomList values (2,6,23,0)")
    cur.execute("insert into RTIDevicePageData values (100,1,10,1,0)")
    cur.execute("insert into RTIDevicePageData values (101,1,11,1,1)")
    cur.execute("insert into RTIDevicePageData values (381,116,11,6,0)")
    cur.execute("insert into RTIDevicePageData values (396,116,13,6,1)")
    cur.execute("insert into RTIDevicePageData values (397,116,12,6,1)")
    cur.execute("insert into RTIDevicePageData values (395,116,14,6,2)")
    cur.execute("insert into Layers values (200,100,1,300,0,1,'',0,null,0)")
    cur.execute("insert into Layers values (201,101,1,301,0,1,'',0,null,0)")
    cur.execute("insert into Layers values (202,381,2,302,0,1,'',0,null,23)")
    cur.execute("insert into SharedLayers values (300,'Page Layer')")
    cur.execute("insert into SharedLayers values (301,'Home Layer')")
    cur.execute("insert into SharedLayers values (302,'RK3 Layer')")

    cur.execute("insert into ButtonTagNames values (114,'LIGHTS - Load 2 Level')")
    cur.execute("insert into ButtonTagNames values (129,'LIGHTS - Load 2 TOGGLE')")
    cur.execute("insert into ButtonTagNames values (130,'WRAPPER - Sense Test')")
    cur.execute("insert into ButtonTagNames values (131,'SENSE - Gate Open')")
    cur.execute("insert into ButtonTagNames values (140,'Driver Action A')")
    cur.execute("insert into ButtonTagNames values (141,'Driver Action B')")
    cur.execute("insert into ButtonTagNames values (142,'Driver Action Leak')")
    cur.execute("insert into ButtonTagNames values (143,'SENSE - Driveway High')")
    cur.execute("insert into ButtonTagNames values (150,'Old Slider')")
    cur.execute("insert into ButtonTagNames values (151,'Condition Graphic')")
    cur.execute("insert into ButtonTagNames values (152,'Shop [Preview]')")
    cur.execute("insert into ButtonTagNames values (153,'Browse')")
    cur.execute("insert into ButtonTagNames values (154,'Activity: Home')")
    cur.execute("insert into ButtonTagNames values (155,'Activity: Apple TV 1 (Bed 2)')")
    cur.execute("insert into ButtonTagNames values (156,'Activity: Sat 1 (Bed 2)')")
    cur.execute("insert into ButtonTagNames values (157,'Activity: Samsung TV (Bed 2)')")

    cur.execute("insert into RTIDeviceButtonData values (246,300,0,114,0,140,30,46,284,'',10,9,20,320,46,284,1,0)")
    cur.execute("insert into RTIDeviceButtonData values (247,300,1,129,0,140,334,46,76,'',10,7,20,620,46,76,2,0)")
    cur.execute("insert into RTIDeviceButtonData values (248,300,2,150,0,210,30,46,120,'',10,5,90,320,46,120,1,0)")
    cur.execute("insert into RTIDeviceButtonData values (249,300,3,151,0,260,30,46,120,'',10,6,140,320,46,120,1,0)")
    cur.execute("insert into RTIDeviceButtonData values (250,300,4,152,0,310,30,46,120,'',10,14,190,320,46,120,1,0)")
    cur.execute("insert into RTIDeviceButtonData values (251,300,5,153,0,360,30,120,220,'',10,8,240,320,120,220,1,0)")
    cur.execute("insert into RTIDeviceButtonData values (252,300,6,154,0,40,30,46,120,'',10,0,40,320,46,120,1,0)")
    cur.execute("insert into RTIDeviceButtonData values (260,302,0,155,0,53,88,112,160,'1',12,0,160,200,112,160,1,0)")
    cur.execute("insert into RTIDeviceButtonData values (261,302,1,156,0,213,88,112,160,'2',12,0,320,200,112,160,1,0)")
    cur.execute("insert into RTIDeviceButtonData values (262,302,2,157,0,373,88,112,160,'',12,0,480,200,112,160,1,0)")

    cur.execute("insert into Variables values (1,0,-1,114,'$%VARIABLE!x@DDL002%$','token@DDL002',null,null,null)")
    cur.execute("insert into Variables values (2,0,-1,129,null,'token@DDS002',null,null,null)")
    cur.execute("insert into Variables values (3,0,-1,150,null,'slider5@DDL003',null,null,null)")
    cur.execute("insert into Variables values (4,0,-1,151,null,'image6@IMG001',null,null,null)")
    cur.execute("insert into Variables values (5,0,-1,152,null,'image14@IMG014',null,null,null)")
    cur.execute("insert into Variables values (6,0,-1,153,null,'browse8@LIST001',null,null,null)")

    cur.execute("insert into Macros values (362,362,0,-1,129,0)")
    cur.execute("insert into Macros values (400,400,0,-1,130,0)")
    cur.execute("insert into Macros values (401,400,0,-1,131,0)")
    cur.execute("insert into Macros values (402,402,0,-1,143,0)")
    cur.execute("insert into Macros values (500,500,0,-1,0,0)")
    cur.execute("insert into Macros values (501,500,0,99,0,0)")
    cur.execute("insert into Macros values (502,501,0,99,0,0)")
    cur.execute("insert into Macros values (600,600,0,-1,0,0)")
    cur.execute("insert into Macros values (601,600,0,99,0,0)")
    cur.execute("insert into Macros values (700,700,23,-1,155,0)")
    cur.execute("insert into Macros values (701,701,23,-1,0,0)")
    cur.execute("insert into Macros values (702,702,23,-1,156,0)")
    cur.execute("insert into Macros values (703,703,23,-1,157,0)")
    cur.execute("insert into MacroSteps values (1,362,0,1,0,0)")
    cur.execute("insert into MacroSteps values (2,700,0,26,0,0)")
    cur.execute("insert into MacroSteps values (3,700,1,8,0,0)")
    cur.execute("insert into MacroSteps values (4,701,0,8,0,0)")
    cur.execute("insert into MacroSteps values (5,702,0,26,0,0)")
    cur.execute("insert into MacroSteps values (6,702,1,8,0,0)")
    cur.execute("insert into MacroSteps values (7,703,0,26,0,0)")
    cur.execute("insert into MacroSteps values (8,703,1,8,0,0)")
    cur.execute("insert into MacroStepsView values (10,501,0,14,140,null,null,null,null,null,null,null,null,null,null,null)")
    cur.execute("insert into MacroStepsView values (11,501,1,14,141,null,null,null,null,null,null,null,null,null,null,null)")
    cur.execute("insert into MacroStepsView values (12,502,0,14,142,null,null,null,null,null,null,null,null,null,null,null)")
    cur.execute("insert into MacroStepsView values (13,601,0,1,null,null,null,'setSelLyr:1','G1L0','','','',1,null,null,null)")
    cur.execute("insert into MacroStepsView values (2,700,0,26,null,null,null,null,null,null,null,null,null,null,null,null)")
    cur.execute("insert into MacroStepsView values (3,700,1,8,null,null,null,null,null,null,null,null,null,'6,6',null,null)")
    cur.execute("insert into MacroStepsView values (4,701,0,8,null,null,null,null,null,null,null,null,null,'6',null,null)")
    cur.execute("insert into MacroStepsView values (5,702,0,26,null,null,null,null,null,null,null,null,null,null,null,null)")
    cur.execute("insert into MacroStepsView values (6,702,1,8,null,null,null,null,null,null,null,null,null,'6,6,6',null,null)")
    cur.execute("insert into MacroStepsView values (7,703,0,26,null,null,null,null,null,null,null,null,null,null,null,null)")
    cur.execute("insert into MacroStepsView values (8,703,1,8,null,null,null,null,null,null,null,null,null,'6,6,6',null,null)")
    cur.execute("insert into MacroSelectSource values (2,248,23)")
    cur.execute("insert into MacroSelectSource values (5,250,23)")
    cur.execute("insert into MacroSelectSource values (7,249,23)")
    cur.execute("insert into MacroPageLink values (3,2,397,1,1,0,0)")
    cur.execute("insert into MacroPageLink values (6,2,396,1,1,0,0)")
    cur.execute("insert into MacroPageLink values (8,2,395,1,1,0,0)")
    cur.execute("insert into MacroPageLinkView values (3,'381,397','6,6')")
    cur.execute("insert into MacroPageLinkView values (4,'397','6')")
    cur.execute("insert into MacroPageLinkView values (6,'381,396,397','6,6,6')")
    cur.execute("insert into MacroPageLinkView values (8,'381,395,397','6,6,6')")
    cur.execute("insert into PortLabels values (1,0,-65024,'Gate')")
    cur.execute("insert into PortLabels values (3,0,-65023,'Driveway')")
    cur.execute("insert into PortLabels values (2,0,66048,'Sense 1')")
    cur.execute("insert into SenseModeMap values (1,0,-1,1)")
    cur.execute("insert into Events values (1,1,400,'Sense Test',1,0,0,-1,null,null,0,null,0,0,null,null)")
    cur.execute("insert into Events values (4,1,402,'Voltage Sense Test',1,1,1,-1,null,null,0,null,0,0,null,null)")
    cur.execute("insert into Events values (6,3,401,'',1,null,null,null,null,null,1,X'0000000000000000',127,0,null,null)")
    cur.execute("insert into Events values (7,3,402,'',1,null,null,null,null,null,1,X'0000000000000100',127,0,null,null)")
    cur.execute("insert into Events values (2,5,362,'Driver Test',1,null,null,null,null,null,0,null,0,0,99,'fallback')")
    cur.execute("insert into Events values (3,5,500,'Driver Multi',1,null,null,null,null,null,0,null,0,0,99,'multi')")
    cur.execute("insert into Events values (5,5,600,'Driver Command',1,null,null,null,null,null,0,null,0,0,99,'startup')")
    cur.execute(
        """insert into DriverData values (
        99,
        1,
        1,
        'Driver Name',
        '<functions><category name="Layers"><function name="Ex. Group: %%grpNm1%%" export="setSelLyr:1"><parameter name="Layer:" type="mcstring"><choice name="None" value="G1L0"/></parameter></function></category></functions>',
        '<events><category name="General"><event name="fallback" tag="fallback"/></category><category name="Routine"><event name="multi" tag="multi"/></category><category name="%%grpNm1%%"><event name="startup" tag="startup"/></category></events>'
        )"""
    )
    cur.execute("insert into DriverConfig values (1,99,'grpNm1','DISPLAY')")
    cur.execute("insert into PageLinks values (1,1,129,0,101)")
    cur.execute("insert into PageLinks values (2,1,154,1,999)")
    cur.execute("insert into Activities values (1,23,248,1,1,701)")

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
            system_event = data["events"]["system"][0]
            voltage_event = data["events"]["system"][1]
            sunrise_event = data["events"]["system"][2]
            sunset_event = data["events"]["system"][3]
            driver_event = data["events"]["driver"][0]
            driver_multi = data["events"]["driver"][1]
            driver_command = data["events"]["driver"][2]
            page = data["devices"][0]["userFacing"]["pages"][0]
            layer = page["layers"][0]
            buttons = {btn["buttonIdentity"]["buttonTagName"]: btn for btn in layer["buttonCategories"]["screenButtons"]}
            slider = buttons["LIGHTS - Load 2 Level"]
            toggle = buttons["LIGHTS - Load 2 TOGGLE"]
            old_slider = buttons["Old Slider"]
            image6 = buttons["Condition Graphic"]
            image14 = buttons["Shop [Preview]"]
            browse = buttons["Browse"]
            activity_home = buttons["Activity: Home"]
            rk3_page = data["devices"][1]["userFacing"]["pages"][0]
            rk3_layer = rk3_page["layers"][0]
            rk3_buttons = {btn["buttonIdentity"]["buttonTagName"]: btn for btn in rk3_layer["buttonCategories"]["screenButtons"]}
            activity_apple = rk3_buttons["Activity: Apple TV 1 (Bed 2)"]
            activity_sat = rk3_buttons["Activity: Sat 1 (Bed 2)"]
            activity_samsung = rk3_buttons["Activity: Samsung TV (Bed 2)"]
            self.assertEqual(system_event["userFacing"]["description"], "Sense Test")
            self.assertEqual(system_event["userFacing"]["resolvedTrigger"], "When Gate closes")
            self.assertEqual(system_event["userFacing"]["macroName"], "SENSE - Gate Open")
            self.assertEqual(system_event["userFacing"]["macroNames"], ["SENSE - Gate Open"])
            self.assertEqual(system_event["userFacing"]["commandNames"], [])
            self.assertEqual(system_event["userFacing"]["testTargets"], {"Trigger": True, "Macro": True})
            self.assertEqual(voltage_event["userFacing"]["description"], "Voltage Sense Test")
            self.assertEqual(voltage_event["userFacing"]["resolvedTrigger"], "When Driveway goes High")
            self.assertEqual(voltage_event["userFacing"]["macroName"], "SENSE - Driveway High")
            self.assertEqual(sunrise_event["userFacing"]["description"], "")
            self.assertEqual(sunrise_event["userFacing"]["resolvedTrigger"], "At Sunrise")
            self.assertEqual(sunset_event["userFacing"]["description"], "")
            self.assertEqual(sunset_event["userFacing"]["resolvedTrigger"], "At Sunset")
            self.assertEqual(driver_event["userFacing"]["driverName"], "IST-5 (Global)")
            self.assertEqual(driver_event["userFacing"]["driverCategory"], "General")
            self.assertEqual(driver_event["userFacing"]["resolvedTrigger"], "fallback")
            self.assertEqual(driver_event["userFacing"]["firstActionName"], "LIGHTS - Load 2 TOGGLE")
            self.assertEqual(driver_event["userFacing"]["resolvedActions"], {"macros": ["LIGHTS - Load 2 TOGGLE"], "macroSteps": []})
            self.assertEqual(driver_event["userFacing"]["macroStepCount"], 0)
            self.assertEqual(driver_event["userFacing"]["testTargets"], {"Trigger": True, "Macro": True})
            self.assertNotIn("macroName", driver_event["userFacing"])
            self.assertNotIn("macroNames", driver_event["userFacing"])
            self.assertEqual(driver_multi["userFacing"]["driverCategory"], "Routine")
            self.assertEqual(driver_multi["userFacing"]["resolvedTrigger"], "multi")
            self.assertEqual(driver_multi["userFacing"]["firstActionName"], "Driver Action A")
            self.assertEqual(driver_multi["userFacing"]["resolvedActions"], {"macros": ["Driver Action A", "Driver Action B"], "macroSteps": []})
            self.assertEqual(driver_command["userFacing"]["driverCategory"], "DISPLAY")
            self.assertEqual(driver_command["userFacing"]["resolvedTrigger"], "startup")
            self.assertEqual(driver_command["userFacing"]["firstActionName"], "Ex. Group: DISPLAY: None")
            self.assertEqual(
                driver_command["userFacing"]["resolvedActions"],
                {"macros": [], "macroSteps": [{"name": "Ex. Group: DISPLAY: None", "type": "command"}]},
            )
            self.assertEqual(driver_command["userFacing"]["macroStepCount"], 1)
            self.assertEqual(driver_command["userFacing"]["testTargets"], {"Trigger": True, "MacroStep": True})
            self.assertEqual(driver_multi["userFacing"]["macroStepCount"], 0)
            self.assertEqual(driver_multi["userFacing"]["testTargets"], {"Trigger": True, "Macros": True})
            self.assertTrue(slider["buttonUI"]["orientations"]["portrait"]["visible"])
            self.assertFalse(slider["buttonUI"]["orientations"]["landscape"]["visible"])
            self.assertEqual(slider["buttonUI"]["orientations"]["portrait"]["coordinates"]["left"], 30)
            self.assertEqual(slider["buttonUI"]["orientations"]["landscape"]["coordinates"]["left"], 320)
            self.assertFalse(toggle["buttonUI"]["orientations"]["portrait"]["visible"])
            self.assertTrue(toggle["buttonUI"]["orientations"]["landscape"]["visible"])
            self.assertEqual(toggle["buttonUI"]["orientations"]["portrait"]["coordinates"]["left"], 334)
            self.assertEqual(toggle["buttonUI"]["orientations"]["landscape"]["coordinates"]["left"], 620)
            self.assertTrue(slider["testTargets"]["variables"]["Value"])
            self.assertFalse(slider["testTargets"]["variables"]["State"])
            self.assertFalse(slider["testTargets"]["variables"]["Command"])
            self.assertFalse(slider["testTargets"]["pageLink"])
            self.assertEqual(slider["buttonUI"]["stack"], {"layerOrder": 0, "buttonOrder": 0, "frameNumber": 0})
            self.assertEqual(toggle["buttonUI"]["stack"], {"layerOrder": 0, "buttonOrder": 1, "frameNumber": 0})
            self.assertTrue(toggle["testTargets"]["pageLink"])
            self.assertEqual(toggle["resolvedPageLink"], {"targetPageId": 101, "targetPageName": "Home", "resolutionPath": "directPageLink"})
            self.assertEqual(old_slider["buttonIdentity"]["buttonType"], "Slider")
            self.assertTrue(old_slider["testTargets"]["variables"]["Value"])
            self.assertFalse(old_slider["testTargets"]["variables"]["Command"])
            self.assertEqual(image6["buttonIdentity"]["buttonType"], "Image")
            self.assertTrue(image6["testTargets"]["variables"]["Image"])
            self.assertEqual(image14["buttonIdentity"]["buttonType"], "Image")
            self.assertTrue(image14["testTargets"]["variables"]["Image"])
            self.assertIsNone(browse["buttonIdentity"]["buttonType"])
            self.assertFalse(browse["testTargets"]["variables"]["Value"])
            self.assertFalse(browse["testTargets"]["variables"]["State"])
            self.assertFalse(browse["testTargets"]["variables"]["Command"])
            self.assertTrue(browse["testTargets"]["variables"]["List"])
            self.assertTrue(activity_home["testTargets"]["pageLink"])
            self.assertEqual(activity_home["resolvedPageLink"], {"targetPageId": 100, "targetPageName": "Lights", "resolutionPath": "directPageLink"})
            self.assertTrue(activity_apple["testTargets"]["pageLink"])
            self.assertTrue(activity_apple["testTargets"]["macroSteps"])
            self.assertEqual(activity_apple["resolvedPageLink"], {"targetPageId": 397, "targetPageName": "Apple TV 1", "resolutionPath": "macroStep"})
            self.assertTrue(activity_sat["testTargets"]["pageLink"])
            self.assertEqual(activity_sat["resolvedPageLink"], {"targetPageId": 396, "targetPageName": "Sat TV 1", "resolutionPath": "macroStep"})
            self.assertTrue(activity_samsung["testTargets"]["pageLink"])
            self.assertEqual(activity_samsung["resolvedPageLink"], {"targetPageId": 395, "targetPageName": "TV Controls", "resolutionPath": "macroStep"})
            diag_buttons = {btn["buttonTagName"]: btn for btn in data["devices"][0]["diagnostics"]["pages"][0]["buttons"] if btn["buttonTagName"]}
            browse_diag = diag_buttons["Browse"]
            self.assertEqual(browse_diag["buttonTagName"], "Browse")
            self.assertTrue(browse_diag["testTargets"]["variableDetails"]["List"]["enabled"])
            self.assertEqual(browse_diag["testTargets"]["variableDetails"]["List"]["source"], "ObjectData")
            self.assertEqual(browse_diag["testTargets"]["variableDetails"]["List"]["objectRef"], "browse8@LIST001")
            self.assertFalse(browse_diag["testTargets"]["variableDetails"]["Command"]["enabled"])
            self.assertIsNone(browse_diag["testTargets"]["variableDetails"]["Command"]["driverFunction"])
            self.assertEqual(
                browse_diag["source"],
                {"layerId": 200, "sharedLayerId": 300, "layerOrder": 0, "buttonOrder": 5, "frameNumber": 0},
            )

    def test_extract_single_size_device_uses_fallback_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            apex = td_path / "sample.apex"
            schema = td_path / "apex_project_structure.json"
            schema.write_text("{}", encoding="utf-8")
            create_test_apex(
                apex,
                supported_orientations=3,
                portrait_width=0,
                portrait_height=0,
                landscape_width=0,
                landscape_height=0,
                screen_width=480,
                screen_height=640,
            )

            run = subprocess.run(
                [sys.executable, str(EXTRACT), "--apex", str(apex), "--project-structure", str(schema), "--out-dir", str(td_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            data = json.loads((td_path / "sample_project_data.json").read_text(encoding="utf-8"))
            device_ui = data["devices"][0]["userFacing"]["deviceUI"]
            self.assertEqual(device_ui["portrait"], {"supported": True, "resolution": {"width": 480, "height": 640}})
            self.assertEqual(device_ui["landscape"], {"supported": False, "resolution": {"width": 0, "height": 0}})

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
                                                    "variables": {"Text": False, "Reversed": False, "Inactive": False, "Visible": False, "Value": True, "State": False, "Command": True, "Image": False, "List": False},
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

            home_html = (td_path / "sample_project_data__project-home.html").read_text(encoding="utf-8")
            html = (td_path / "sample_project_data__device-0-ist-5-global.html").read_text(encoding="utf-8")
            manifest = json.loads((td_path / "sample_project_data__project-manifest.json").read_text(encoding="utf-8"))
            device_payload = json.loads((td_path / "sample_project_data__device-0-ist-5-global__payload.json").read_text(encoding="utf-8"))
            self.assertIn("Project Home", home_html)
            self.assertIn("System Events", home_html)
            self.assertIn("Driver Events", home_html)
            self.assertIn("Devices", home_html)
            self.assertIn("sample_project_data__device-0-ist-5-global.html", home_html)
            self.assertIn("IST-5 (Global) - Lights", html)
            self.assertIn("class='project-home-link' href='sample_project_data__project-home.html'", html)
            self.assertIn("Variable - Value", html)
            self.assertIn(">Btn</button>", html)
            self.assertIn("const APP_UI_CONTROLS=", html)
            self.assertIn("const RTI_DEVICE_LAYOUT=", html)
            self.assertIn("const VIEWPORT_NAV=", html)
            self.assertIn("const ZOOM_CONTROLS=", html)
            self.assertIn("const sourceSize=currentOrientationSize();", html)
            self.assertIn("const widthScale=rtiCanvasWidth/sourceSize.width;", html)
            self.assertIn("const heightScale=rtiCanvasHeight/sourceSize.height;", html)
            self.assertIn("let scale=Math.min(widthScale,heightScale);", html)
            self.assertIn("id='rtiCanvas'", html)
            self.assertIn("id='rtiDeviceCanvas'", html)
            self.assertIn("orientationControls.style.width", html)
            self.assertIn("layerControls.style.width", html)
            self.assertIn("const controls={", html)
            self.assertIn("const rtiCanvasWidth=Math.max(appWidth-controls.left-controls.right,1);", html)
            self.assertIn("const rtiCanvasHeight=Math.max(appHeight-controls.top-controls.bottom,1);", html)
            self.assertIn("rtiCanvas.style.left=`${controls.left}px`;", html)
            self.assertIn("rtiCanvas.style.top=`${controls.top}px`;", html)
            self.assertIn(".app-ui-controls{position:absolute;box-sizing:border-box;z-index:20;}", html)
            self.assertIn(".vp-nav{width:44px;height:44px", html)
            self.assertIn("id='zoomControls'", html)
            self.assertIn("class='zoom-btn zoom-dec'", html)
            self.assertIn("class='zoom-btn zoom-reset'", html)
            self.assertIn("class='zoom-btn zoom-inc'", html)
            self.assertIn("<div class='zoom-controls' id='zoomControls'>", html)
            self.assertIn("const ZOOM_DEFAULT=100;", html)
            self.assertIn("const ZOOM_MAX=300;", html)
            self.assertIn("const ZOOM_STEP=10;", html)
            self.assertIn("let currentViewportIndexes=VP_FRAMES.map(()=>0);", html)
            self.assertIn("function applyViewportState()", html)
            self.assertIn("if (el.classList.contains('vp-btn')) {", html)
            self.assertIn("applyViewportState();", html)
            self.assertIn("id='rtiContent'", html)
            self.assertIn("rtiCanvas.classList.toggle('scroll-hover'", html)
            self.assertIn("scrollbar-gutter:stable overlay;", html)
            self.assertIn("rtiCanvasEl.addEventListener('scroll', applyRtiLayout, {passive:true});", html)
            self.assertIn("width:min(560px,calc(100vw - 24px))", html)
            self.assertIn(".row{box-sizing:border-box;width:100%;", html)
            self.assertIn("textarea{display:block;box-sizing:border-box;width:100%;max-width:100%;", html)
            self.assertIn("textarea placeholder='Fail note (required for Fail)' style='min-height:70px;'", html)
            self.assertNotIn("textarea placeholder='Fail note' style='width:100%;min-height:70px;'", html)
            self.assertEqual(manifest.get("format"), "sentinel-testing-payload-v1")
            self.assertEqual(manifest.get("projectStem"), "sample_project_data")
            self.assertEqual(manifest.get("projectHomeHtml"), "sample_project_data__project-home.html")
            self.assertEqual(len(manifest.get("devices", [])), 1)
            self.assertEqual(manifest["devices"][0].get("deviceName"), "IST-5 (Global)")
            self.assertEqual(manifest["devices"][0].get("payloadFile"), "sample_project_data__device-0-ist-5-global__payload.json")
            self.assertEqual(device_payload.get("format"), "sentinel-testing-payload-v1")
            self.assertEqual(device_payload.get("deviceIndex"), 0)
            self.assertEqual(device_payload.get("deviceName"), "IST-5 (Global)")
            self.assertEqual(len(device_payload.get("pages", [])), 1)
            self.assertEqual(device_payload["pages"][0].get("pageName"), "Lights")
            self.assertEqual(device_payload["pages"][0].get("pageIndex"), 0)
            self.assertTrue(isinstance(device_payload["pages"][0].get("layers"), list))

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
            self.assertTrue((td_path / "sample_project_data__project-home.html").exists())
            self.assertTrue((td_path / "sample_project_data__device-0-ist-5-global.html").exists())
            self.assertTrue((td_path / "sample_project_data__project-manifest.json").exists())
            self.assertTrue((td_path / "sample_project_data__device-0-ist-5-global__payload.json").exists())
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
            self.assertTrue((td_path / "sample_project_data__project-home.html").exists())
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
                                            "resolvedPageLink": {"targetPageId": 200},
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
            home_html = (td_path / "sample_project_data__project-home.html").read_text(encoding="utf-8")
            html = (td_path / "sample_project_data__device-0-ist-5-global.html").read_text(encoding="utf-8")
            self.assertIn("sample_project_data__device-0-ist-5-global.html", home_html)
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
                                                                "buttonUI": orientation_ui(10, 140, 334, 46, 76, l_top=70, l_left=200, l_height=40, l_width=60),
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
            self.assertIn("data-p-left='354'", html)
            self.assertIn("data-p-top='200'", html)
            self.assertIn("data-l-left='210'", html)
            self.assertIn("data-l-top='100'", html)

    def test_generate_uses_single_size_device_ui_for_source_size(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data = {
                "devices": [
                    {
                        "userFacing": {
                            "displayName": "RK3-V (Bedroom1)",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 640}},
                                "landscape": {"supported": False, "resolution": {"width": 0, "height": 0}},
                            },
                            "pages": [
                                {
                                    "pageName": "Home",
                                    "layers": [
                                        {
                                            "layerName": "Hard Keys",
                                            "layerOrder": 0,
                                            "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []},
                                            "viewports": [],
                                        }
                                    ],
                                }
                            ],
                        },
                        "diagnostics": {"deviceId": 1, "pages": [{"pageId": 100, "pageName": "Home"}]},
                    }
                ]
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            html = (td_path / "sample_project_data__device-0-rk3-v-bedroom1.html").read_text(encoding="utf-8")
            self.assertIn("const SOURCE_DEVICE_SIZE={width:480,height:640};", html)
            self.assertIn('const ORIENTATION_STATE={"current": "portrait", "options": ["portrait"], "sizes": {"portrait": {"width": 480, "height": 640}, "landscape": {"width": 854, "height": 480}}};', html)

    def test_generate_project_home_includes_event_sections_and_device_links(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data = {
                "source": {"file": r"C:\\Projects\\sample.apex", "extractedAtUtc": "2026-03-13T00:00:00Z", "scriptVersion": "0.1.0"},
                "events": {
                    "system": [
                        {
                            "userFacing": {
                                "eventType": "Sense",
                                "description": "Hall Motion",
                                "resolvedTrigger": "When Hall Sensor opens",
                                "macroName": "Hall Lights",
                                "macroNames": ["Hall Lights"],
                                "commandNames": [],
                                "testTargets": {"Trigger": True, "Macro": True},
                            }
                        },
                        {
                            "userFacing": {
                                "eventType": "Scheduled",
                                "description": "",
                                "resolvedTrigger": "At Sunrise",
                                "macroName": "Outside Lights [Off]",
                                "macroNames": ["Outside Lights [Off]"],
                                "commandNames": [],
                                "testTargets": {"Trigger": True, "Macro": True},
                            }
                        }
                    ],
                    "driver": [
                        {
                            "userFacing": {
                                "eventType": "Driver",
                                "driverName": "Lutron Driver",
                                "driverCategory": "General",
                                "resolvedTrigger": "Button 1",
                                "firstActionName": "Scene On",
                                "resolvedActions": {
                                    "macros": [],
                                    "macroSteps": [
                                        {"name": "Scene On", "type": "command"},
                                        {"name": "Scene Off", "type": "command"},
                                    ],
                                },
                                "macroStepCount": 2,
                                "testTargets": {"Trigger": True, "MacroSteps": True},
                            }
                        },
                        {
                            "userFacing": {
                                "eventType": "Driver",
                                "driverName": "Lutron Driver",
                                "driverCategory": "Pathway",
                                "resolvedTrigger": "Button 2",
                                "firstActionName": "Path Lights",
                                "resolvedActions": {
                                    "macros": ["Path Lights"],
                                    "macroSteps": [
                                        {"name": "Scene Raise", "type": "command"},
                                        {"name": "Scene Lower", "type": "command"},
                                    ],
                                },
                                "macroStepCount": 2,
                                "testTargets": {"Trigger": True, "Macro": True, "MacroSteps": True},
                            }
                        },
                        {
                            "userFacing": {
                                "eventType": "Driver",
                                "driverName": "Venstar Driver",
                                "driverCategory": "Garage",
                                "resolvedTrigger": "State Change",
                                "firstActionName": "",
                                "resolvedActions": {
                                    "macros": [],
                                    "macroSteps": [
                                        {"name": "", "type": "undefined"},
                                        {"name": "", "type": "undefined"},
                                        {"name": "", "type": "undefined"},
                                        {"name": "", "type": "undefined"},
                                        {"name": "", "type": "undefined"},
                                    ],
                                },
                                "macroStepCount": 5,
                                "testTargets": {"Trigger": True, "MacroSteps": True},
                            }
                        }
                    ],
                },
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
                    },
                    {
                        "userFacing": {
                            "displayName": "XP-6s",
                            "deviceUI": {
                                "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                                "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                            },
                            "pages": [],
                        },
                        "diagnostics": {"deviceId": 2, "pages": []},
                    },
                ],
            }
            project_path = td_path / "sample_project_data.json"
            ui_path = td_path / "app_ui_structure.json"
            project_path.write_text(json.dumps(project_data), encoding="utf-8")
            ui_path.write_text(json.dumps(sample_app_ui()), encoding="utf-8")

            run = subprocess.run([sys.executable, str(GENERATE), "--project-data", str(project_path), "--app-ui", str(ui_path), "--out-dir", str(td_path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)

            home_html = (td_path / "sample_project_data__project-home.html").read_text(encoding="utf-8")
            self.assertIn("System Events | 2 events", home_html)
            self.assertIn("Driver Events | 3 events", home_html)
            self.assertIn("Devices", home_html)
            self.assertIn('"Hall Motion" | When Hall Sensor opens, run macro: Hall Lights', home_html)
            self.assertIn("At Sunrise, run macro: Outside Lights [Off]", home_html)
            self.assertIn("Lutron Driver", home_html)
            self.assertIn("When General / Button 1 happens, run macro steps: Scene On ...+1 more", home_html)
            self.assertIn("When Pathway / Button 2 happens, run actions: Path Lights ...+2 more", home_html)
            self.assertIn("When Garage / State Change happens, run 5 undefined macro steps", home_html)
            self.assertIn('"targets": ["Trigger", "Macro"]', home_html)
            self.assertIn('"targets": ["Trigger", "MacroSteps"]', home_html)
            self.assertIn('"targets": ["Trigger", "Macro", "MacroSteps"]', home_html)
            self.assertIn("id='system-events' hidden", home_html)
            self.assertIn("id='driver-events' hidden", home_html)
            self.assertIn("aria-expanded='false'", home_html)
            self.assertIn("onclick='toggleSection(this)'", home_html)
            self.assertIn("<span class='section-chevron' aria-hidden='true'><svg viewBox='0 0 16 16'><path d='M3.5 6.25 8 10.75 12.5 6.25'/></svg></span>", home_html)
            self.assertIn("width:min(560px,calc(100vw - 24px))", home_html)
            self.assertIn("textarea{display:block;box-sizing:border-box;width:100%;max-width:100%;", home_html)
            self.assertIn("textarea placeholder='Fail note (required for Fail)' style='min-height:70px;'", home_html)
            self.assertNotIn("textarea placeholder='Fail note' style='width:100%;min-height:70px;'", home_html)
            self.assertNotIn("??", home_html)
            self.assertIn("sample_project_data__device-0-ist-5-global.html", home_html)
            self.assertNotIn("sample_project_data__device-1-xp-6s.html", home_html)


if __name__ == "__main__":
    unittest.main()
