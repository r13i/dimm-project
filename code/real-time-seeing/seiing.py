from random import*
import numpy as np
import math
import statistics
import matplotlib.pyplot as plt
print('Veuillez entrer du diamètre des ouvertures extérieures du GDIMM')

d= input()
d=float(d)

print('Veuillez entrer la distance séparant les deux orifices')
l=input()
l=float(l)
print('Veuillez entrer la longieur d onde' )
lamda = input()
lamda = float(lamda)

print('Veuillez entrer angle zénithal ')
z=input()
z = float(z)

b=l/d
kl=0.364*(1-0.532*(b**-1/3)-0.024*(b**-(7/3)))
kt=0.364*(1-0.798*(b**-1/3)-0.024*(b**-(7/3)))
# cx1 coordonné selon x of the first centroide au cour du temps
# cx2  coordonné selon x of the second centroide au cour du temps
# cy1 coordonné selon yof the first centroide au cour du temps
# # cy2 coordonné selon yof the second centroide au cour du temps
cx1 = []
cx2 = []
cy1 =[]
cy2 =[]

seeingl=[] # seeing longitudinal
seeingt=[] # seeing transversal
seeingm=[] # seeing moyeneé
for c in range(20):
    # remplir d'une manieire aleatoire  les coordonnées
    cx1.append(randint(1,4))
    cx2.append(4+randint(1, 4))
    cy1.append(randint(1, 4))
    cy2.append(randint(1, 4))


deltax =[]
deltay =[]
for i in range (20):
    deltax.append(cx2[i]-cx1[i])
    deltay.append(cy2[i] - cy1[i])
m=0
n=0

std1=[] # standar deviation selon x
std2=[] # standar deviation selon y
print(deltax)
print(deltay)
if(len(deltax)>9): # on fait le calcul sur 9 echentillons
    for i in range(len(deltax)-9):
        # campute the standar deviation  (sigma x et sigma y)

        m = statistics.mean(deltax[i:11 + i])

        std1.append(statistics.stdev(deltax[i:11 + i], m))
        n = statistics.mean(deltay[i:11 + i])
        std2.append(statistics.stdev(deltay[i:11 + i], m))
        # calcul  of the seeings
        seeingl.append(0.98*(((d/lamda)*(std1[i]/kl))**0.2)*(math.cos(z)**0.6))
        seeingt.append(0.98 * (((d / lamda) * (std2[i] / kt)) ** 0.2) * (math.cos(z) ** 0.6))
        seeingm.append(0.5*(seeingl[i]+seeingt[i]))
print(seeingt)
print(seeingl)
print(seeingm)
plt.title("seeings variation 4")
plt.plot([1,2,3,4,5,6,7,8,9,10,11], seeingl , "r--",linewidth=0.8, marker="*", label="seeingt")

plt.plot([1,2,3,4,5,6,7,8,9,10,11], seeingt, "bs", linewidth=0.8, marker="*", label="seeingt")
plt.plot([1,2,3,4,5,6,7,8,9,10,11], seeingm, "g^", linewidth=0.8, marker="+", label="seeingm")
plt.xlabel('seeings')
plt.ylabel('Temps')
plt.show()



