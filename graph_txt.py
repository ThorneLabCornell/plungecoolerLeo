''' a quick graphing script. disregard. '''
import numpy as np
import matplotlib.pyplot as plt

def moving_average(a, n=3):
    ret = np.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n

if __name__ == '__main__':
    values = np.zeros(200000)
    path = "C:\\Users\\ret-admin\\Desktop\\plunge_data\\temp\\"
    path += input()
    path+= ".txt"
    f = open(path, 'r')
    i = 0
    for line in f:
        values[i] = (float(line) - 1.26669097) / 0.00376052
        i += 1

    avgs = moving_average(values, 50)

    x = np.linspace(1, avgs.size, avgs.size)

    plt.title("Line graph")
    plt.xlabel("X axis")
    plt.ylabel("Y axis")
    plt.scatter(x, avgs, s=2, color="black")
    plt.axhline(y=0, color='r', linestyle='-')
    plt.axhline(y=-93, color='r', linestyle='-')
    plt.show()