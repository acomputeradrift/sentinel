# Project Structure

Locked on: 2026-03-09

```json
{
  "source": {
    "file": "path/to/project.apex",
    "extractedAtUtc": "2026-03-09T00:00:00Z"
  },
  "events": {
    "system": [
      {
        "userFacing": {
          "eventType": "Sense | Scheduled | Startup",
          "resolvedTrigger": ""
        },
        "diagnostics": {
          "eventId": 0,
          "enabled": true,
          "macro": {
            "systemMacroId": 0,
            "macroId": 0,
            "scope": {
              "roomId": 0,
              "roomName": "Global",
              "deviceId": -1,
              "deviceName": null
            },
            "buttonTagName": null
          }
        }
      }
    ],
    "driver": [
      {
        "userFacing": {
          "eventType": "Driver",
          "resolvedTrigger": ""
        },
        "diagnostics": {
          "eventId": 0,
          "enabled": true,
          "driverId": 0,
          "driverName": "",
          "driverExtraString": "",
          "macro": {
            "systemMacroId": 0,
            "macroId": 0,
            "scope": {
              "roomId": 0,
              "roomName": "Global",
              "deviceId": 0,
              "deviceName": ""
            },
            "buttonTagName": null
          }
        }
      }
    ]
  },
  "devices": [
    {
      "userFacing": {
        "displayName": "iPhone",
        "pages": [
          {
            "pageName": "",
            "buttonCategories": {
              "screenLabels": [
                {
                  "buttonIdentity": {
                    "buttonTagName": null,
                    "text": "Now Playing"
                  },
                  "buttonUI": {
                    "fontSize": 12,
                    "coordinates": {
                      "top": 0,
                      "left": 0,
                      "height": 0,
                      "width": 0
                    }
                  },
                  "testTargets": {
                    "text": true,
                    "macro": false,
                    "variables": {
                      "Reversed": false,
                      "Inactive": false,
                      "Visible": false,
                      "Value": false,
                      "State": false,
                      "Command": false
                    },
                    "textVariable": false,
                    "pageLink": false
                  }
                }
              ],
              "screenButtons": [
                {
                  "buttonIdentity": {
                    "buttonTagName": "POWER - TV ON",
                    "text": "Power"
                  },
                  "buttonUI": {
                    "fontSize": 7,
                    "coordinates": {
                      "top": 0,
                      "left": 0,
                      "height": 0,
                      "width": 0
                    }
                  },
                  "testTargets": {
                    "text": true,
                    "macro": true,
                    "variables": {
                      "Reversed": true,
                      "Inactive": true,
                      "Visible": false,
                      "Value": false,
                      "State": false,
                      "Command": false
                    },
                    "textVariable": false,
                    "pageLink": false
                  }
                }
              ],
              "hardButtons": []
            }
          }
        ]
      },
      "diagnostics": {
        "deviceId": 0,
        "deviceName": "iPhone",
        "displayName": "iPhone",
        "rtiAddress": 0,
        "isClonedController": false,
        "pages": [
          {
            "pageId": 0,
            "pageName": "",
            "pageOrder": 0,
            "pageNumber": 1,
            "uiItems": [
              {
                "buttonId": 0
              }
            ],
            "buttons": [
              {
                "buttonId": 0,
                "buttonTagName": "POWER - TV ON",
                "identifiers": {
                  "buttonTagId": 0,
                  "text": "Power"
                },
                "testTargets": {
                  "label": null,
                  "macro": {
                    "scope": "Global",
                    "scopeType": "Global | Room | Source | Controller",
                    "globalMacroId": null,
                    "deviceMacroId": null,
                    "resolvedCommand": null,
                    "isEmpty": false
                  },
                  "variables": [
                    {
                      "variableId": 0,
                      "scope": "Global | Room | Source | Controller",
                      "scopeType": "Global | Room | Source | Controller",
                      "type": "ObjectData | ReversedData | InactiveData | VisibleData",
                      "rawToken": "",
                      "resolvedName": null
                    }
                  ],
                  "textVariable": {
                    "scope": "Global",
                    "scopeType": "Global | Room | Source | Controller",
                    "rawButtonText": null,
                    "resolvedName": null,
                    "format": {
                      "falseLabel": null,
                      "trueLabel": null
                    }
                  },
                  "pageLink": {
                    "pageLinkId": null,
                    "targetPageId": null,
                    "targetPageName": null
                  }
                }
              }
            ]
          }
        ]
      }
    }
  ]
}
```
