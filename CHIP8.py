import sys
import pygame
import numpy
import random
import time

#constants
SCREEN_WIDTH = 64
SCREEN_HEIGHT = 32
SCREEN_MULTIPLIER = 10
FONT_START = 0x050
PROGRAM_START = 0x200
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

FONT = [
    0xF0, 0x90, 0x90, 0x90, 0xF0, # 0
    0x20, 0x60, 0x20, 0x20, 0x70, # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0, # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0, # 3
    0x90, 0x90, 0xF0, 0x10, 0x10, # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0, # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0, # 6
    0xF0, 0x10, 0x20, 0x40, 0x40, # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0, # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0, # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90, # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0, # B
    0xF0, 0x80, 0x80, 0x80, 0xF0, # C
    0xE0, 0x90, 0x90, 0x90, 0xE0, # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0, # E
    0xF0, 0x80, 0xF0, 0x80, 0x80  # F
]

KEY_CODES = {
    0x1: pygame.K_1, 0x2: pygame.K_2, 0x3: pygame.K_3, 0xC: pygame.K_4, # 1 2 3 4
    0x4: pygame.K_q, 0x5: pygame.K_w, 0x6: pygame.K_e, 0xD: pygame.K_r, # Q W E R
    0x7: pygame.K_a, 0x8: pygame.K_s, 0x9: pygame.K_d, 0xE: pygame.K_f, # A S D F
    0xA: pygame.K_z, 0x0: pygame.K_x, 0xB: pygame.K_c, 0xF: pygame.K_v, # Z X C V
}

class CHIP8:
    def __init__(self, filename):
        self.initialize_memory()
        self.load_font()
        self.load_program(filename)
        self.launch_window()

    #initialize memory,stack,  counters and registers
    def initialize_memory(self):
        self.memory = numpy.zeros(4096, dtype=int)  #4kB = 4096B
        self.regs = numpy.zeros(16, dtype=int)      #16 general registers
        self.PC = PROGRAM_START                     #program counter
        self.I = 0                                  #index register
        self.stack = []

        self.prev_frame = [0] * 16                  #used for saving key states in FX0A instruction

        self.delay_timer = 0
        self.sound_timer = 0
        self.timer_start = time.time()

    #load font into memory (0x050 - 0x09F)
    def load_font(self):
        pc = FONT_START
        for byte in FONT:
            self.memory[pc] = byte
            pc += 1

    #load program instructions into memory, starting from 0x200
    def load_program(self, filename):
        pc = PROGRAM_START
        file = open(filename, mode="rb")

        while True:
            byte = file.read(1)
            if not byte:
                break
            else:
                self.memory[pc] = int.from_bytes(byte, "big")
                pc += 1

    #launch pygame window and scale size up
    def launch_window(self):
        pygame.init()
        self.window = pygame.display.set_mode((SCREEN_WIDTH * SCREEN_MULTIPLIER, SCREEN_HEIGHT * SCREEN_MULTIPLIER))
        self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.running = True

    #Stops the loop if window has been closed
    def check_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False

    #check how much time has passed since last loop, and substract from timers if they're greater than 0
    #TERRIBLE implementation but it'll do for now
    def check_timers(self):
        timer_end = time.time()
        if self.delay_timer > 0:
            self.delay_timer -= (timer_end - self.timer_start) * 60
        if self.sound_timer > 0:
            self.sound_timer -= (timer_end - self.timer_start) * 60
        self.timer_start = time.time()

    #take two bytes from memory, combine them into one instruction and return
    def fetch_instruction(self):
        instruction = (self.memory[self.PC] << 8) | self.memory[self.PC + 1]
        self.PC += 2
        return instruction
    
    #Decode an instruction and do whatever it wants to do
    def decode_and_execute(self, instr):
        #Splitting instruction for easier access to certain parts/digits
        
        opcode = instr >> 12        #First nibble
        VX = (instr >> 8) & 0x0F    #Second nibble
        VY = (instr >> 4) & 0x00F   #Third nibble
        N = instr & 0x000F          #Fourth nibble
        NN = instr & 0x00FF         #Second byte
        NNN = instr & 0x0FFF        #Second, third and fourth nibbles

        VF = 15                     #Alias for flag register

        match opcode:
            case 0x0:
                #00E0 - clear the screen
                if NNN == 0x0E0:
                    self.screen.fill(0)
                #00EE - pop value from stack and assign it to PC
                elif NNN == 0x00EE:
                    self.PC = self.stack.pop()
            case 0x1:
                #1NNN - set value NNN to PC
                self.PC = NNN
            case 0x2:
                #2NNN - push PC value to stack, set PC to NNN
                self.stack.append(self.PC)
                self.PC = NNN
            case 0x3:
                #3XNN - Skip instruction if X is equal to NN
                if self.regs[VX] == NN:
                    self.PC += 2
            case 0x4:
                #4XNN - Skip instruction if X is NOT equal to NN
                if self.regs[VX] != NN:
                    self.PC += 2
            case 0x5:
                #5XY0 - Skip instruction if X and Y values are equal
                if self.regs[VX] == self.regs[VY]:
                    self.PC += 2
            case 0x6:
                #6XNN - Set register X to value NN
                self.regs[VX] = NN
            case 0x7:
                #7XNN - Add value NN to register X
                self.regs[VX] = (self.regs[VX] + NN) & 0xFF
            case 0x8:
                #Logical and arithemtic instructions
                match N:
                    #8XY0 - Assign value
                    case 0x0:
                        self.regs[VX] = self.regs[VY]
                    #8XY1 - Binary OR
                    case 0x1:
                        self.regs[VX] |= self.regs[VY]
                    #8XY2 - Binary AND
                    case 0x2:
                        self.regs[VX] &= self.regs[VY]
                    #8XY3 - Logical OR
                    case 0x3:
                        self.regs[VX] ^= self.regs[VY]
                    #8XY4 - Add, set flag register to 1 or 0, whether X register has overflown
                    case 0x4:
                        carry = 1 if (self.regs[VX] + self.regs[VY] > 255) else 0
                        self.regs[VX] = (self.regs[VX] + self.regs[VY]) & 0xFF
                        self.regs[VF] = carry
                    #8XY5 - Substract (VX = VX - VY)
                    case 0x5:
                        not_borrow = 1 if (self.regs[VX] >= self.regs[VY]) else 0
                        self.regs[VX] = (self.regs[VX] - self.regs[VY]) & 0xFF
                        self.regs[VF] = not_borrow
                    #8XY6 - Shift X one bit (right)
                    case 0x6:
                        shifted_out = self.regs[VX] & 0b1
                        self.regs[VX] = self.regs[VX] >> 1
                        self.regs[VF] = shifted_out
                    #8XY7 - Substract, X = Y - X
                    case 0x7:
                        not_borrow = 1 if (self.regs[VY] >= self.regs[VX]) else 0
                        self.regs[VX] = (self.regs[VY] - self.regs[VX]) & 0xFF
                        self.regs[VF] = not_borrow
                    #8XYE - Shift X one bit (left)
                    case 0xE:
                        shifted_out = (self.regs[VX] >> 7) & 0b1
                        self.regs[VX] = (self.regs[VX] << 1) & 0xFF
                        self.regs[VF] = shifted_out
            case 0x9:
                #9XY0 - Skip instruction if X and Y values are NOT equal
                if self.regs[VX] != self.regs[VY]:
                    self.PC += 2
            case 0xA:
                #ANNN - set value NNN to register I
                self.I = NNN
            case 0xB:
                #BNNN - Jump with offset
                self.PC = NNN + self.regs[0]
            case 0xC:
                #CXNN - Generate random number, binary AND it with NN and store result in X
                rand_number = random.randint(0, 255) & NN
                self.regs[VX] = rand_number
            case 0xD:
                #DXYN - Display
                x_pos = self.regs[VX] % 64  #coordinates of when to draw sprite
                y_pos = self.regs[VY] % 32
                rows = N                    #number of sprite's rows
                sprite = self.I             #location of a sprite in memory
                self.regs[VF] = 0           #set VF to 0 at the start of instruction

                for i in range(rows):
                    if (y_pos + i > 31): break  #stop the drawing if sprite sticks out from the window
                    byte = self.memory[sprite] #get one byte from memory, representing one row of a sprite (8 pixels)
                    sprite += 1
                    bit_filter = 7
                    for j in range(8):
                        if (x_pos + j > 63): break #stop the drawing and go to the next row if sprite sticks out from the window
                        bit = (byte & (1 << bit_filter)) >> bit_filter #filter out individual bits from byte, starting from left/msb
                        bit_filter -= 1
                        if bit == 1:    #flip the pixel - black goes white, white goes black 
                            if self.screen.get_at((x_pos + j, y_pos + i)) == BLACK:
                                color = WHITE
                            elif self.screen.get_at((x_pos + j, y_pos + i)) == WHITE:
                                color = BLACK
                                self.regs[VF] = 1   #if any pixel was 'turned off', set VF to 1
                            pygame.draw.rect(self.screen, color, (x_pos + j, y_pos + i, 1, 1))
                
                self.window.blit(pygame.transform.scale(self.screen, self.window.get_rect().size), (0, 0))
                pygame.display.update()
            case 0xE:
                key = self.regs[VX]
                is_pressed = pygame.key.get_pressed()
                #EX9E - Skip if key in X is pressed
                if NN == 0x9E:
                    if is_pressed[KEY_CODES[key]]:
                        self.PC += 2
                #EXA1 - Skip if key in X is NOT pressed
                elif NN == 0xA1:
                    if not is_pressed[KEY_CODES[key]]:
                        self.PC += 2
            case 0xF:
                match NN:
                    #FX07 - Set VX to value of delay timer
                    case 0x07:
                        self.regs[VX] = self.delay_timer
                    #FX15 - Set delay timer to value of VX
                    case 0x15:
                        self.delay_timer = self.regs[VX]
                    #FX18 - Set sound timer to value of VX
                    case 0x18:
                        self.sound_timer = self.regs[VX]
                    #FX1E - Add VX value to I register
                    case 0x1E:
                        self.I += self.regs[VX]
                        if self.I > 0xFFF:
                            self.regs[VF] = 1
                    #FX0A - Loop forever until a key is pressed.
                    #       If it's pressed and released, its keycode is saved in VX and execution continues
                    case 0x0A:
                        input = False
                        is_pressed = pygame.key.get_pressed()
                        for key, val in KEY_CODES.items():
                            if not is_pressed[val] and self.prev_frame[key]:
                                self.regs[VX] = key
                                input = True
                                self.prev_frame[key] = 0
                                break
                            elif is_pressed[val]:
                                self.prev_frame[key] = 1
                        if not input:
                            self.PC -= 2
                    #FX29 - Sets I register to memory address of a given font character
                    case 0x29:
                        char_location = 0x050 + ((self.regs[VX] & 0x0F) * 5)
                        self.I = char_location
                    #FX33 - Cuts VX value into three individual digits and stores it in memory at addressess I, I+1, I+2
                    #       Example: VX = 256, mem[I] = 2, mem[I+1] = 5, mem[I+2] = 6
                    case 0x33:
                        number = self.regs[VX]
                        divider = 100
                        for i in range(3):
                            self.memory[self.I + i] = int(number // divider % 10)
                            divider /= 10
                    #FX55 - Takes values from V0 - VX 
                    #       Stores them in memory at addresses mem[I] - mem[I + X] respectively
                    case 0x55:
                        index = self.I
                        for i in range(VX + 1):
                            self.memory[index] = self.regs[i]
                            index += 1
                    #FX65 - Takes values from memory at addresses mem[I] - mem[I + X]
                    #       Stores them in V0 - VX respectively
                    case 0x65:
                        index = self.I
                        for i in range(VX + 1):
                            self.regs[i] = self.memory[index]
                            index += 1

    def close_window(self):
        pygame.quit()
        exit()


ch8 = CHIP8(sys.argv[1])

while ch8.running:
    time.sleep(0.001)   #makes emulator run at ~700 instructions per second
    ch8.check_events()
    ch8.check_timers()
    instr = ch8.fetch_instruction()
    ch8.decode_and_execute(instr)
    
ch8.close_window()