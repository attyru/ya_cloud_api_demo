# importing only  those functions 
# which are needed 
from tkinter import * 
from tkinter.ttk import * 
from time import strftime 
  
# creating tkinter window 
root = Tk() 
root.title('Resizable') 
root.geometry('250x100') 
  
Label(root, text = 'It\'s resizable').pack(side = TOP, pady = 10) 
  
# Allowing root window to change 
# it's size according to user's need 
root.resizable(True, True) 
  
mainloop() 