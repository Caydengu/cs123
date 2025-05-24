# karel_test.py

import karel

 # pupper.bark()

def square(pupper):
    pupper.move()
    pupper.turn_right()
    pupper.move()
    pupper.turn_right()
    pupper.move()
    pupper.turn_right()
    pupper.move()
    pupper.turn_right()

def forward_turnaround(pupper):
    pupper.bark()
    pupper.bark()
    pupper.move()
    pupper.turn_left()
    pupper.turn_left()
    pupper.move()
    pupper.turn_left()
    pupper.turn_left()

def main():
    pupper = karel.KarelPupper()
    forward_backward(pupper)
   # forward_backward(pupper)
   # square(pupper)

   # pupper.turn_left()
   # pupper.turn_left()

    #forward_backward(pupper)

   # pupper.turn_left()
   # pupper.turn_left()

   # forward_backward(pupper)
    

if __name__ == '__main__':
    main()
