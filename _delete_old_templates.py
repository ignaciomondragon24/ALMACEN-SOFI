import os
base = 'c:/Users/nacho/Desktop/CHE GOLOSO/che goloso/templates/signage/'
for f in ['home.html', 'history.html', 'template_list.html']:
    path = base + f
    if os.path.exists(path):
        os.remove(path)
        print(f'Deleted: {f}')
    else:
        print(f'Not found: {f}')
print('DONE')
# List remaining
remaining = os.listdir(base) if os.path.isdir(base) else []
print(f'Remaining files: {remaining}')
# Self-delete
os.remove(__file__)
