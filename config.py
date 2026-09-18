"""Visual constants and campaign definitions copied from the supplied original."""
RED = '#F82408'
NAVY = '#0F1011'
STEEL = '#4D5C6A'
GREEN = '#15803D'
AMBER = '#B45309'
PLUM = '#6D28D9'
PAGE_SIZE = 20
CAMPAIGNS = [{'id': '701TR00000tTIebYAG',
  'event': 'namer',
  'label': 'NAMER Registration',
  'abbr': 'Reg',
  'isParent': True},
 {'id': '701TR000017I31KYAS',
  'event': 'namer',
  'label': 'Floor Scan',
  'abbr': 'Floor'},
 {'id': '701TR0000179AenYAE',
  'event': 'namer',
  'label': 'Executive Meeting',
  'abbr': 'Exec'},
 {'id': '701TR000016ovjzYAA',
  'event': 'namer',
  'label': 'ERP ROI Calculator',
  'abbr': 'ROI'},
 {'id': '701TR000016z9X3YAI',
  'event': 'namer',
  'label': 'Attendee QR Code',
  'abbr': 'QR'},
 {'id': '701TR00000ttfUHYAY',
  'event': 'emea',
  'label': 'EMEA Registration',
  'abbr': 'Reg',
  'isParent': True},
 {'id': '701TR0000179FuaYAE',
  'event': 'emea',
  'label': 'Executive Meeting',
  'abbr': 'Exec'},
 {'id': '701TR000017R4SnYAK',
  'event': 'emea',
  'label': 'Floor Scan',
  'abbr': 'Floor'}]
FAMILIES = {'namer': {'label': 'Champions of Manufacturing — NAMER',
           'dates': 'Sept 21–23, 2026 · Chicago',
           'parentId': '701TR00000tTIebYAG',
           'childIds': ['701TR000017I31KYAS',
                        '701TR0000179AenYAE',
                        '701TR000016ovjzYAA',
                        '701TR000016z9X3YAI']},
 'emea': {'label': 'Champions of Manufacturing — EMEA',
          'dates': 'Oct 8–9, 2026 · Munich',
          'parentId': '701TR00000ttfUHYAY',
          'childIds': ['701TR0000179FuaYAE', '701TR000017R4SnYAK']}}
ENGAGED_STATUSES = set(['engaged', '02 - registered (member)', '04 - attended tradeshow (member)', '06 - attended session (success)', '06 - significant conversation (success)', '06 - spoke to sales (success)', 'member', '02 - completed', '03 - completed-hand raise', '02-clicked link', 'responded', '03 - clicked link (member)', '04 - accessed content (success)', '03 - took action (success)', '03 - completed (success)', 'clicked', '04 - took action (success)', '02 - registered (member)', '03 - attended (success)', '04-significant conversation', 'registered', 'visited booth', 'influenced', 'attended', 'attended on-demand', 'filled-out form', 'replied'])
CAMPAIGN_BY_ID = {c["id"]: c for c in CAMPAIGNS}
FAMILY_MAP = {c["id"]: c["event"] for c in CAMPAIGNS}
