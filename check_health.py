from dotenv import load_dotenv
load_dotenv()

import asyncio
import sys
sys.path.insert(0, '.')

from hyperspace.providers.registry import ProviderRegistry

async def main():
    reg = ProviderRegistry.from_config('config/providers.yaml')
    health = await reg.get_health_all()
    
    print('=' * 80)
    print(f'{"Provider":30s} {"Status":20s} {"Score":6s}  备注')
    print('=' * 80)
    for pid, h in health.items():
        print(f'{pid:30s} {h.status.value:20s} {h.score:5.0f}   {h.message}')
    print('=' * 80)
    print(f'共 {len(health)} 个 Provider')

asyncio.run(main())