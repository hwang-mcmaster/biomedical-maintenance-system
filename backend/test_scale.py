"""Opt-in real PostgreSQL inventory checks at 50/100/200 records."""
import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from app import repository
from app.database import get_connection
from app.schemas import EquipmentCreate
from live_test_support import authenticated_fixture
from test_equipment import PAYLOAD


@unittest.skipUnless(os.getenv('RUN_SCALE_TESTS')=='1','Set RUN_SCALE_TESTS=1 for temporary 200-record PostgreSQL fixtures.')
class InventoryScaleTests(unittest.TestCase):
    def test_inventory_at_50_100_200(self):
        client=authenticated_fixture(self)
        token=uuid4().hex
        ids=[];results=[]
        try:
            for target in (50,100,200):
                payloads=[]
                for i in range(len(ids),target):
                    identifier=uuid4();ids.append(identifier)
                    device=EquipmentCreate.model_validate(PAYLOAD|{'asset_tag':f'VALIDATE-{token}-{i:03}',
                      'serial_number':f'000{token}{i:03}','repair_events':i%25})
                    payloads.append((identifier,*repository.values(device)))
                columns=['equipment_id',*repository.FIELD_COLUMNS.values()]
                with get_connection() as c:
                    c.cursor().executemany(f"INSERT INTO equipment ({','.join(columns)}) VALUES ({','.join(['%s']*len(columns))})",payloads)
                start=perf_counter();response=client.get('/api/equipment');elapsed=(perf_counter()-start)*1000
                self.assertEqual(response.status_code,200,response.text)
                owned=[r for r in response.json() if r['id'] in {str(i) for i in ids}]
                self.assertEqual(len(owned),target)
                self.assertTrue(all(r['serial_number'].startswith('000') for r in owned))
                sample=client.get('/api/equipment/'+str(ids[-1]))
                self.assertEqual(sample.status_code,200,sample.text)
                results.append({'fixture_records':target,'total_inventory_records':len(response.json()),
                  'list_api_ms':round(elapsed,2),'response_bytes':len(response.content),'detail_verified':True})
        finally:
            with get_connection() as c:
                c.execute('DELETE FROM equipment WHERE equipment_id=ANY(%s)',(ids,))
                remaining=c.execute('SELECT count(*) AS n FROM equipment WHERE equipment_id=ANY(%s)',(ids,)).fetchone()['n']
            self.assertEqual(remaining,0)
        output={'generated_at':datetime.now(timezone.utc).isoformat(),
          'scope':'Authenticated in-process FastAPI requests against real PostgreSQL. Includes auth and DB latency; excludes browser/network transport. Test data inserted directly as explicitly labelled fixtures. CRUD and real AI workflow are tested separately.',
          'scenarios':results,'fixture_equipment_cleanup_verified':True}
        target=Path(__file__).parent/'validation/scale-api-results.json'
        target.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
