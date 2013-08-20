# Uitility script that may be useful when trying to find memory leaks
# or other memory related problems.

allocations = set()

for line in open('meminfo.txt'):
    (_, command, address) = line.split()
    if (command == 'malloc_new') or (command == 'malloc_copy'):
        allocations.add(address)
    elif command == 'free':
        if not address in allocations:
            print address + ' not found in allocations!'
        else:
            allocations.remove(address)

if allocations:
    print 'Allocations remain: ' + str(len(allocations))
    print 'Those are: ' + str(allocations)