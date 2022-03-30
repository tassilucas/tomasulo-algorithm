import sys

'''
Load/Store -> 2 Cycles
Add/Sub ->  4  Cycles
Mul/Div -> 6 Cycles
'''

pc = 0

store_latency = 2
load_latency = 2
add_latency = 4
mul_latency = 6

instructions = []
r_register = [0] * 32
fp_register = [0] * 32
memory = [0] * 128

load_buffer = {'Load' + str(i): {'busy': False, 'A': 0, 'Vj': 0, 'Qj': 0, 'ready': False, 'result': 0, 'issue': 0, 'executing': False} for i in range(0, 3)}
store_buffer = {'Store' + str(i): {'busy': False, 'A': 0, 'Vk': 0, 'Qk': 0, 'ready': False, 'result': 0, 'issue': 0, 'executing': False} for i in range(0, 2)}
rs_add = {'Add' + str(i): {'busy': False, 'oper': 0, 'Vj': 0, 'Vk': 0, 'Qj': 0, 'Qk': 0, 'ready': False, 'result': 0, 'issue': 0, 'executing': False} for i in range(0, 3)}
rs_mul = {'Mul' + str(i): {'busy': False, 'oper': 0, 'Vj': 0, 'Vk': 0, 'Qj': 0, 'Qk': 0, 'ready': False, 'result': 0, 'issue': 0, 'executing': False} for i in range(0, 2)}
rs_branch = {'Branch' + str(i): {'busy': False, 'oper': 0, 'Vj': 0, 'Vk': 0, 'Qj': 0, 'Qk': 0, 'ready': False, 'result': 0, 'issue': 0, 'label': 0, 'executing': False} for i in range(0, 1)}

registerstat = [0] * 32

queue_ld = []
queue_sd = []

clock = 0
issue_count = 0

checkpoint_ld = 0
checkpoint_sd = 0

load_processing = False
store_processing = False

rs_add_processing = {'Add0': 0, 'Add1': 0, 'Add2': 0}
rs_add_checkpoint = {'Add0': 0, 'Add1': 0, 'Add2': 0}

rs_mul_processing = {'Mul0': 0, 'Mul1': 0}
rs_mul_checkpoint = {'Mul0': 0, 'Mul1': 0}

rs_branch_processing = {'Branch0': 0}
rs_branch_checkpoint = {'Branch0': 0}

branch_wait = False

def peek(q):
    if q:
        return q[0]
    else:
        return None

def convert_data(data):
    return int(data,  2)

def read_instructions_file(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if not line.startswith('#'):
                instructions.append(line.strip('\n'))

def read_instructions_input():
    while True:
        input_instruction = input("Digite instrução")
        if input_instruction == 'end':
            break
        instructions.append(input_instruction)

def instruction_fetch(instructions):
    try:
        return instructions[pc]
    except:
        return 'None'

# add.d: 0, sub.d: 1, mul.d: 2, div.d: 3
def find_rtype_operands(inst):
    return {
        'op': inst[:6],
        'fmt': inst[6:11],
        'ft': convert_data(inst[11:16]),
        'fs': convert_data(inst[16:21]),
        'fd': convert_data(inst[21:26]),
        'oper': inst[-6:],
        'type': 'R'
    }

def find_itype_operands_load(inst):
    return {
        'op': inst[:6],
        'base': convert_data(inst[6:11]),
        'rt': convert_data(inst[11:16]),
        'imm': convert_data(inst[16:]),
        'type': 'I'
    }

def find_itype_operands_branch(inst):
    return {
        'op': inst[:6],
        'rs': convert_data(inst[6:11]),
        'rt': convert_data(inst[11:16]),
        'offset': convert_data(inst[16:]),
        'type': 'I-B'
    }

def instruction_decode(inst):
    op = inst[:6]
    # r-type instructions
    if op == '010001':
        return find_rtype_operands(inst)

    # sd/ld instruction
    if op == '111111' or op == '110111':
        return find_itype_operands_load(inst)

    # beq instruction
    if op == '000100' or op == '000101' or op == '010101':
        return find_itype_operands_branch(inst)

    return {'inst': 'error'}

'''
add.d -> 000000
sub.d -> 000001
mul.d -> 000010
div.d -> 000011
'''
def place_rtype(di):
    op = di['oper']

    if op == '000000' or op == '000001':
        for k, r in rs_add.items():
            if r['busy'] == False:
                if registerstat[di['fs']] != 0:
                    r['Qj'] = registerstat[di['fs']]
                else:
                    r['Vj'] = fp_register[di['fs']]
                    r['Qj'] = 0

                if registerstat[di['ft']] != 0:
                    r['Qk'] = registerstat[di['ft']]
                else:
                    r['Vk'] = fp_register[di['ft']]
                    r['Qk'] = 0

                r['oper'] = op
                r['busy'] = True
                r['issue'] = issue_count
                registerstat[di['fd']] = k
                return k

    if op == '000010' or op == '000011':
        for k, r in rs_mul.items():
            if r['busy'] == False:
                if registerstat[di['fs']] != 0:
                    r['Qj'] = registerstat[di['fs']]
                else:
                    r['Vj'] = fp_register[di['fs']]
                    r['Qj'] = 0

                if registerstat[di['ft']] != 0:
                    r['Qk'] = registerstat[di['ft']]
                else:
                    r['Vk'] = fp_register[di['ft']]
                    r['Qk'] = 0

                r['oper'] = op
                r['busy'] = True
                r['issue'] = issue_count
                registerstat[di['fd']] = k
                return k

def loadstore_operation(di, buffer):
    for k, slot in buffer.items():
        if slot['busy'] == False:
            slot['Vj'] = r_register[di['base']]
            slot['Qj'] = 0
            slot['A'] = di['imm']
            slot['busy'] = True
            slot['issue'] = issue_count

            # Load operation
            if di['op'] == '110111':
                registerstat[di['rt']] = k
                queue_ld.append(k)
            # Store operation
            else:
                if registerstat[di['rt']] != 0:
                    slot['Qk'] = registerstat[di['rt']]
                else:
                    slot['Vk'] = fp_register[di['rt']]
                    slot['Qk'] = 0
                queue_sd.append(k)

            return k

def place_itype(di):
    if di['op'] == '111111':
        return loadstore_operation(di, store_buffer)
    elif di['op'] == '110111':
        return loadstore_operation(di, load_buffer)

def place_ibtype(di):
    global branch_wait

    for k, slot in rs_branch.items():
        if slot['busy'] == False:
            if registerstat[di['rs']] != 0:
                slot['Qj'] = registerstat[di['rs']]
            else:
                slot['Vj'] = fp_register[di['rs']]
                slot['Qj'] = 0

            # Verifica também se não é uma BEQZ (que não possuí segundo operando rt)
            if registerstat[di['rt']] != 0 and di['op'] != '010101':
                slot['Qk'] = registerstat[di['rt']]
            else:
                if di['op'] == '010101':
                    slot['Vk'] = 0
                else:
                    slot['Vk'] = fp_register[di['rt']]
                slot['Qk'] = 0

            slot['oper'] = di['op']
            slot['busy'] = True
            slot['label'] = di['offset']
            slot['issue'] = issue_count
            branch_wait = True
            return k

def instruction_issue(di):
    global clock, issue_count
    if di['type'] == 'I':
        print("{} -> {}".format(clock, place_itype(di)))
    elif di['type'] == 'R':
        print("{} -> {}".format(clock, place_rtype(di)))
    elif di['type'] == 'I-B':
        print("{} -> {}".format(clock, place_ibtype(di)))

    issue_count += 1

def shift_load_buffer(buffer, name):
    buffer[name]['busy'] = False
    buffer[name]['A'] = 0
    buffer[name]['Vj'] = 0
    buffer[name]['Qj'] = 0
    buffer[name]['ready'] = False
    buffer[name]['result'] = 0
    buffer[name]['executing'] = False
    print(name, " finalizado e escrito no clock ", clock)

def clean_r(rs, r, branch):
    rs[r]['busy'] = False
    rs[r]['op'] = 0
    rs[r]['Vj'] = 0
    rs[r]['Vk'] = 0
    rs[r]['Qj'] = 0
    rs[r]['Qk'] = 0
    rs[r]['ready'] = False
    rs[r]['result'] = 0
    rs[r]['executing'] = False

    if(branch):
        rs[r]['label'] = 0
    print(r, " finalizado e escrito no clock ", clock)

def perform_add(info):
    if info['oper'] == '000000':
        return info['Vj'] + info['Vk']
    elif info['oper'] == '000001':
        return info['Vj'] - info['Vk']

def perform_mul(info):
    if info['oper'] == '000010':
        return info['Vj'] * info['Vk']
    elif info['oper'] == '000011':
        return info['Vj'] / info['Vk']

def execute_stage():
    global load_processing, store_processing, checkpoint_ld, checkpoint_sd

    p = peek(queue_ld)
    if p != None:
        if branch_wait and load_buffer[p]['issue'] < rs_branch['Branch0']['issue'] or not branch_wait:
            if load_buffer[p]['busy'] == True and load_buffer[p]['Qj'] == 0:
                if load_processing == False:
                    checkpoint_ld = clock
                    load_buffer[p]['executing'] = True
                    load_processing = True
                elif clock - checkpoint_ld == load_latency:
                    load_buffer[p]['ready'] = True
                    load_buffer[p]['A'] = load_buffer[p]['Vj'] + load_buffer[p]['A']
                    load_buffer[p]['result'] = memory[load_buffer[p]['A']]
                    print("Executed. Result ld rs: ({}) {}".format(p, load_buffer[p]['A'], clock))
                    load_processing = False

    st = peek(queue_sd)
    if st != None:
        if branch_wait and store_buffer[st]['issue'] < rs_branch['Branch0']['issue'] or not branch_wait:
            if store_buffer[st]['busy'] == True and store_buffer[st]['Qk'] == 0:
                if store_processing == False:
                    checkpoint_sd = clock
                    store_buffer[st]['executing'] = True
                    store_processing = True
                elif clock - checkpoint_sd == store_latency:
                    store_buffer[st]['ready'] = True
                    store_buffer[st]['A'] = store_buffer[st]['Vj'] + store_buffer[st]['A']
                    store_buffer[st]['result'] = store_buffer[st]['A']
                    print("Executed. Result ld rs: ({}) {}".format(st, store_buffer[st]['A'], clock))
                    store_processing = False
    
    # Executing pending add.d/sub.d instruction
    for r, info in rs_add.items():
        if branch_wait and rs_add[r]['issue'] < rs_branch['Branch0']['issue'] or not branch_wait:
            if info['busy'] == True and info['Qj'] == info['Qk'] == 0:
                if info['oper'] == '000000' or info['oper'] == '000001':
                    if rs_add_processing[r] == False:
                        rs_add_checkpoint[r] = clock
                        info['executing'] = True
                        rs_add_processing[r] = True
                    elif clock - rs_add_checkpoint[r] == add_latency:
                        info['ready'] = True
                        info['result'] = perform_add(info)
                        print("Executed. Result add rs: ({}) {}".format(r, info['result'], clock))
                        rs_add_processing[r] = False

    # Executing pending mul.d/div.d instruction
    for r, info in rs_mul.items():
        if branch_wait and rs_mul[r]['issue'] < rs_branch['Branch0']['issue'] or not branch_wait:
            if info['busy'] == True and info['Qj'] == info['Qk'] == 0:
                if info['oper'] == '000010' or info['oper'] == '000011':
                    if rs_mul_processing[r] == False:
                        rs_mul_checkpoint[r] = clock
                        info['executing'] = True
                        rs_mul_processing[r] = True
                    elif clock - rs_mul_checkpoint[r] == mul_latency:
                        info['ready'] = True
                        info['result'] = perform_mul(info)
                        print("Executed. Result mul rs: ({}) {}".format(r, info['result'], clock))
                        rs_mul_processing[r] = False

    # Executing branch instruction
    if branch_wait:
        tmp = rs_branch['Branch0']
        if tmp['Qj'] == tmp['Qk'] == 0:
            tmp['executing'] = True
            if tmp['oper'] == '000100' and tmp['Vj'] - tmp['Vk'] == 0:
                tmp['result'] = 'Take'
            elif tmp['oper'] == '000101' and tmp['Vj'] - tmp['Vk'] != 0:
                tmp['result'] = 'Take'
            elif tmp['oper'] == '010101' and tmp['Vj'] == 0:
                tmp['result'] = 'Take'
            else:
                tmp['result'] = 'Not take'
            tmp['ready'] = True

def write_stage():
    global memory, pc

    for x in range(0, len(registerstat)):
        s = peek(queue_ld)
        if s != None:
            if registerstat[x] == s and load_buffer[s]['ready'] == True:
                fp_register[x] = load_buffer[s]['result']
                registerstat[x] = 0

        for r, v in rs_add.items():
            if registerstat[x] == r and rs_add[r]['ready'] == True:
                fp_register[x] = rs_add[r]['result']
                registerstat[x] = 0

        for r, v in rs_mul.items():
            if registerstat[x] == r and rs_mul[r]['ready'] == True:
                fp_register[x] = rs_mul[r]['result']
                registerstat[x] = 0

    # Solving Add Station pendences j
    for x, r in rs_add.items():
        # Checking with Load Buffer
        s = peek(queue_ld)
        if s != None:
            if load_buffer[s]['ready'] == True and r['Qj'] == s:
                r['Vj'] = load_buffer[s]['result']
                r['Qj'] = 0

        # Checking with Mul Station (remember to ignore same RS)
        for index, mul in rs_mul.items():
            if mul['ready'] == True and r['Qj'] == index:
                r['Vj'] = mul['result']
                r['Qj'] = 0

        # Checking with Add Station
        for index, add in rs_add.items():
            if add['ready'] == True and r['Qj'] == index and index != x:
                r['Vj'] = add['result']
                r['Qj'] = 0

    # Solving Mul Station pendences j
    for x, r in rs_mul.items():
        # Checking with Load Buffer
        s = peek(queue_ld)
        if s != None:
            if load_buffer[s]['ready'] == True and r['Qj'] == s:
                r['Vj'] = load_buffer[s]['result']
                r['Qj'] = 0

        # Checking with Mul Station
        for index, mul in rs_mul.items():
            if mul['ready'] == True and r['Qj'] == index and index != x:
                r['Vj'] = mul['result']
                r['Qj'] = 0

        # Checking with Add Station (remember to ignore same RS)
        for index, mul in rs_add.items():
            if mul['ready'] == True and r['Qj'] == index:
                r['Vj'] = mul['result']
                r['Qj'] = 0

    # Solving Add Station pendences k
    for x, r in rs_add.items():
        # Checking with Load Buffer
        s = peek(queue_ld)
        if s != None:
            if load_buffer[s]['ready'] == True and r['Qk'] == s:
                r['Vk'] = load_buffer[s]['result']
                r['Qk'] = 0

        # Checking with Mul Station (remember to ignore same RS)
        for index, mul in rs_mul.items():
            if mul['ready'] == True and r['Qk'] == index:
                r['Vk'] = mul['result']
                r['Qk'] = 0

        # Checking with Add Station
        for index, add in rs_add.items():
            if add['ready'] == True and r['Qk'] == index and index != x:
                r['Vk'] = add['result']
                r['Qk'] = 0

    # Solving Mul Station pendences k
    for x, r in rs_mul.items():
        # Checking with Load Buffer
        s = peek(queue_ld)
        if s != None:
            if load_buffer[s]['ready'] == True and r['Qk'] == s:
                r['Vk'] = load_buffer[s]['result']
                r['Qk'] = 0

        # Checking with Mul Station (remember to ignore same RS)
        for index, mul in rs_mul.items():
            if mul['ready'] == True and r['Qk'] == index and index != x:
                r['Vk'] = mul['result']
                r['Qk'] = 0

        # Checking with Add Station
        for index, add in rs_add.items():
            if add['ready'] == True and r['Qk'] == index:
                r['Vk'] = add['result']
                r['Qk'] = 0

    # Solving Store Station pendences
    for x, r in store_buffer.items():
        # Checking with Load Buffer
        s = peek(queue_ld)
        if s != None:
            if load_buffer[s]['ready'] and r['Qk'] == s:
                r['Vk'] = load_buffer[s]['result']
                r['Qk'] = 0

        # Checking with Mul Station
        for index, mul in rs_mul.items():
            if mul['ready'] and r['Qk'] == index:
                r['Vk'] = mul['result']
                r['Qk'] = 0

        # Checking with Add station
        for index, add in rs_add.items():
            if add['ready'] and r['Qk'] == index:
                r['Vk'] = add['result']
                r['Qk'] = 0

    # Store condition
    st = peek(queue_sd)
    if st != None and store_buffer[st]['ready'] and store_buffer[st]['Qk'] == 0:
        memory[store_buffer[st]['A']] = store_buffer[st]['Vk']
        store_buffer[st]['busy'] = False

    # Start Branch Station checking
    tmp = rs_branch['Branch0']

    # Checking with Load Buffer
    s = peek(queue_ld)
    if s != None:
        if load_buffer[s]['ready'] == True and tmp['Qj'] == s:
            tmp['Vj'] = load_buffer[s]['result']
            tmp['Qj'] = 0

    # Checking with Mul Station
    for index, mul in rs_mul.items():
        if mul['ready'] == True and tmp['Qj'] == index and index != x:
            tmp['Vj'] = mul['result']
            tmp['Qj'] = 0

    # Checking with Add Station (remember to ignore same RS)
    for index, mul in rs_add.items():
        if mul['ready'] == True and tmp['Qj'] == index:
            tmp['Vj'] = mul['result']
            tmp['Qj'] = 0

    # Checking with Load Buffer
    s = peek(queue_ld)
    if s != None:
        if load_buffer[s]['ready'] == True and tmp['Qk'] == s:
            tmp['Vk'] = load_buffer[s]['result']
            tmp['Qk'] = 0

    # Checking with Mul Station
    for index, mul in rs_mul.items():
        if mul['ready'] == True and tmp['Qk'] == index and index != x:
            tmp['Vk'] = mul['result']
            tmp['Qk'] = 0

    # Checking with Add Station (remember to ignore same RS)
    for index, mul in rs_add.items():
        if mul['ready'] == True and tmp['Qk'] == index:
            tmp['Vk'] = mul['result']
            tmp['Qk'] = 0

    # Branch condition
    if tmp['ready']:
        if tmp['result'] == 'Take':
            print("The branch should be taken and pc will be updated")
            pc = tmp['label']
            print("New PC: {}".format(pc))

    # End branch station checking

'''
This function checks if there is some instruction executing or
to be executed before the branch type instruction
'''
def instruction_before():
    for slot in store_buffer.values():
        if slot['busy'] and not slot['ready']:
            return True

    for slot in rs_add.values():
        if slot['busy'] and not slot['ready']:
            return True

    for slot in rs_mul.values():
        if slot['busy'] and not slot['ready']:
            return True

    return False

def clean_finished_instructions():
    global branch_wait

    if peek(queue_ld) != None and load_buffer[peek(queue_ld)]['ready'] == True:
        shift_load_buffer(load_buffer, queue_ld.pop(0))

    if peek(queue_sd) != None and store_buffer[peek(queue_sd)]['ready'] == True:
        shift_load_buffer(store_buffer, queue_sd.pop(0))

    for r in rs_add.keys():
        if rs_add[r]['ready'] == True:
            clean_r(rs_add, r, False)

    for r in rs_mul.keys():
        if rs_mul[r]['ready'] == True:
            clean_r(rs_mul, r, False)

    if branch_wait and rs_branch['Branch0']['ready'] and not instruction_before():
        clean_r(rs_branch, 'Branch0', True)
        branch_wait = False

'''
This function checks every reservation station to see if
there is any instruction that still executing
'''
def still_execution():
    for slot in load_buffer.values():
        if slot['busy']:
            return True
    for slot in store_buffer.values():
        if slot['busy']:
            return True
    for slot in rs_add.values():
        if slot['busy']:
            return True
    for slot in rs_mul.values():
        if slot['busy']:
            return True
    for slot in rs_branch.values():
        if slot['busy']:
            return True

    # There is no instruction being executed
    return False

def print_fp_registers(print_fp_flag):
    if print_fp_flag:
        print("FP Registers (32) -> {}".format(fp_register))

def print_memory(print_mem_flag):
    if print_mem_flag:
        print("Memory (128) -> {}".format(memory))

def print_load():
    print("+-------------------------------+")
    for k, v in load_buffer.items():
        print("{} -> Busy: {} | Vj: {} | Qj: {} | {}".format(k, v['busy'], v['Vj'], v['Qj'], "EXECUTING" if v['executing'] else " "))
        if k != list(load_buffer.keys())[-1]:
            print("-------------------------------")
    print("+-------------------------------+\n")

def print_store():
    print("+-------------------------------+")
    for k, v in store_buffer.items():
        print("{} -> Busy: {} | Vj: {} | Qj: {} | {}".format(k, v['busy'], v['Vk'], v['Qk'], "EXECUTING" if v['executing'] else " "))
        if k != list(store_buffer.keys())[-1]:
            print("-------------------------------")
    print("+-------------------------------+\n")

def print_rs(rs):
    print("+-------------------------------+")
    for k, v in rs.items():
        print("{} -> Busy: {} | Vj: {} | Vk: {} | Qj: {} | Qk: {} | {}".format(k, v['busy'], v['Vj'], v['Vk'], v['Qj'], v['Qk'], "EXECUTING" if v['executing'] else " "))
        if k != list(rs.keys())[-1]:
            print("-------------------------------")
    print("+-------------------------------+\n")


def print_stations(print_stations_flag):
    if print_stations_flag:
        print("Load Buffer")
        print_load()
        print("Store Buffer")
        print_store()
        print("Reservation Stations")
        print_rs(rs_add)
        print_rs(rs_mul)
        print_rs(rs_branch)
        print("\n")

def pipeline(instructions, step):
    global clock, pc

    while True:
        print("PC: ", pc)
        inst = instruction_fetch(instructions)
        pc += 1

        if inst != 'None':
            di = instruction_decode(inst)
            instruction_issue(di)

        execute_stage()
        write_stage()
        clean_finished_instructions()
        clock += 1

        print_fp_registers(True)
        print_memory(True)
        print_stations(True)

        if not still_execution() and pc >= len(instructions):
            break

        if(step):
            input("Digite algo para prosseguir")

program = int(input("Aperte 1 para digitar programa"))

if program == 1:
    read_instructions_input()
else:
    read_instructions_file(sys.argv[1])

step_input = input("Deseja acompanhar a execucao (y/n)?")

# Loop example
# r_register[1] = 0
# memory[0] = 1
# memory[4] = 0
# memory[8] = 3

if step_input == 'y':
    pipeline(instructions, True)
else:
    pipeline(instructions, False)
