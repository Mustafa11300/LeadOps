from fastapi.testclient import TestClient
import json
from server.app import app
from models import Reward
from utils.score_report import generate_score_report

try:
    client = TestClient(app)

    print('=== Setup Session ===')
    r = client.post('/reset', json={'task_id': 'enrich_lead'})
    sid = r.json()['session_id']
    comp = r.json()['observation']['company_name']
    print('Session ID:', sid)
    print('Company:', comp)

    print('\n=== Test Destructive Penalty ===')
    action_dest = {
        'action_type': 'update',
        'tool_name': 'score_meddic', 
        'thought': 'I am deleting this data',
        'field_updates': {'annual_revenue': None},
        'reason': 'test',
        'confidence': 1.0
    }
    r_dest = client.post('/step', json={'session_id': sid, 'action': action_dest})
    if r_dest.status_code == 200:
        res = r_dest.json()
        comps = res.get('reward', {}).get('components', [])
        for c in comps:
            print(f"  {c['name']}: {c['value']}")

        reward_obj = Reward(**res['reward'])
        print('\n=== Score Report Test ===')
        print(generate_score_report(reward_obj))
    else:
        print('Failed with', r_dest.status_code)
        print(r_dest.text)

except Exception as e:
    import traceback
    traceback.print_exc()
