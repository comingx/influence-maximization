from __future__ import division
from copy import deepcopy
import time, random, operator, os, json, heapq
import networkx as nx
import multiprocessing, numpy
from runIAC import *
import matplotlib.pyplot as plt
from priorityQueue import PriorityQueue as PQ

def findCC(G, Ep):
    # remove blocked edges from graph G
    E = deepcopy(G)
    edge_rem = [e for e in E.edges() if random.random() < (1-Ep[e])**(E[e[0]][e[1]]['weight'])]
    E.remove_edges_from(edge_rem)

    # initialize CC
    CC = dict() # each component is reflection os the number of a component to its members
    explored = dict(zip(E.nodes(), [False]*len(E)))
    c = 0
    # perform BFS to discover CC
    for node in E:
        if not explored[node]:
            c += 1
            explored[node] = True
            CC[c] = [node]
            component = E[node].keys()
            for neighbor in component:
                if not explored[neighbor]:
                    explored[neighbor] = True
                    CC[c].append(neighbor)
                    component.extend(E[neighbor].keys())
    return CC

def findL(CCs, T):
    # find top components that can reach T activated nodes
    sortedCCs = sorted([(len(dv), dk) for (dk, dv) in CCs.iteritems()], reverse=True)
    cumsum = 0 # sum of top components
    L = 0 # current number of CC that achieve T
    # find L first
    for length, numberCC in sortedCCs:
        L += 1
        cumsum += length
        if cumsum >= T:
            break
    return L, sortedCCs

def reverseCCWP(G, Ep, T, min_size):
    '''
     Input:
     G -- undirected graph (nx.Graph)
     T -- coverage size (int)
     Ep -- propagation probabilities (dict)
     r -- ratio for selecting number of components (float)
     Output:
     S -- seed set
    '''
    scores = dict() # initialize scores

    # find CC
    CC = findCC(G, Ep)

    # find L (minimum number of CCs that will achieve T) and sortedCC
    L, sortedCC = findL(CC, T)

    # find number of CC assign scores to
    # (most likely different from L because selects all CCs of size up to min_size)
    QCC = 0 # qualified CCs
    QN = 0 # qualified nodes
    for size, _ in sortedCC:
        if size >= min_size:
            QCC += 1
            QN += size
        else:
            break

    # assign scores to selected CCs
    prev_length  = sortedCC[0][0]
    rank = 1
    for length, numberCC in sortedCC[:QCC]:
        if length != prev_length:
            prev_length = length
            rank += 1
        weighted_score = 1.0/length # updatef = 1
        # weighted_score = 1 # updatef = 2
        # weighted_score = length # updatef = 3
        # weighted_score = 1.0/length**.5 # updatef = 4
        # weighted_score = 1.0/length**2  # updatef = 5
        # weighted_score = L/length # updatef = 6
        # weighted_score = 1.0/(length*L) # updatef = 7
        # weighted_score = 1.0/(1 - (1 - length)*(1 - rank)/(1 - L)) # updatef = 8
        # weighted_score = 1 - (length - 1)*(1 - rank)/(length*(1 - L)) # updatef = 9
        # weighted_score = 1/QN #updatef = 10
        for node in CC[numberCC]:
            scores[node] = weighted_score
    return scores, L

def getScores(G, Ep, T, min_size):
    scores = dict()

    E = deepcopy(G)
    edge_rem = [e for e in E.edges() if random.random() < (1-Ep[e])**(E[e[0]][e[1]]['weight'])]
    E.remove_edges_from(edge_rem)

    # initialize CC
    CCs = dict() # number of a component to its members
    explored = dict(zip(E.nodes(), [False]*len(E)))
    num = 0 # number of CC
    qualified_nodes = []
    qualified_components = []
    CCs_sizes = []
    # perform BFS to discover CC
    for node in E:
        # TODO for some reason using pool.Map tries to access explored[node] that doesn't exist. Strange. Fix later.
        try:
            if not explored[node]:
                num += 1
                explored[node] = True
                CCs[num] = [node]
                try:
                    component = E[node].keys()
                except KeyError:
                    print 'CC:', node
                for neighbor in component:
                    if not explored[neighbor]:
                        explored[neighbor] = True
                        try:
                            CCs[num].append(neighbor)
                        except KeyError:
                            print 'CCs:', num
                        try:
                            component.extend(E[neighbor].keys())
                        except KeyError:
                            print "E_neighbor:", neighbor

                heapq.heappush(CCs_sizes, -len(CCs[num]))
                # assign scores
                size = len(CCs[num])
                if size >= min_size:
                    qualified_components.append(CCs[num])
                    weighted_score = 1.0/size # updatef = 1
                    # weighted_score = 1 # updatef = 2
                    # weighted_score = size # updatef = 3
                    # weighted_score = 1.0/size**.5 # updatef = 4
                    # weighted_score = 1.0/size**2  # updatef = 5
                    for v1 in CCs[num]:
                        qualified_nodes.append(v1)
                        scores[v1] += weighted_score
        except KeyError:
            print 'Explored:', node
            raise

    # normalize scores
    # Q = len(qualified_components)
    # for node in scores:
        # scores[node] *= Q # updatef = 6
        # scores[node] /= Q # updatef = 7

    # determine L
    cumsum = 0
    L = 0
    while cumsum < T:
        size = heapq.heappop(CCs_sizes)
        cumsum -= size
        L += 1

    return scores, L

def updateScores(scores_copied, S, Ep):
    maxk, maxv = max(scores_copied.iteritems(), key=lambda (dk, dv): dv) # top node in the order
    S.append(maxk)
    scores_copied.pop(maxk)
    for v in G[maxk]:
        if v not in S:
            p = Ep[(maxk,v)]
            penalty = (1-p)**(G[maxk][v]['weight'])
            scores_copied[v] *= penalty
                    

# range for floats: http://stackoverflow.com/a/7267280/2069858
def frange(begin, end, step):
    x = begin
    y = end
    while x < y:
        yield x
        x += step

def mapAvgSize (args):
    G, S, Ep, I = args
    return avgIAC(G, S, Ep, I)
def mapReverseCCWP (args):
    G, Ep, T, min_size = args
    return reverseCCWP(G, Ep, T, min_size)

if __name__ == "__main__":
    start = time.time()

    G = nx.read_gpickle("../../graphs/hep.gpickle")
    print 'Read graph G'
    print time.time() - start

    model = "Categories"

    if model == "MultiValency":
        ep_model = "range"
    elif model == "Random":
        ep_model = "random"
    elif model == "Categories":
        ep_model = "degree"

    Ep = dict()
    with open("Ep_hep_%s1.txt" %ep_model) as f:
        for line in f:
            data = line.split()
            Ep[(int(data[0]), int(data[1]))] = float(data[2])

    R = 500
    I = 250
    T = 2500
    print "T:", T
    r = 1
    cpu = multiprocessing.cpu_count()

    updatef = 1
    DROPBOX = "/home/sergey/Dropbox/Influence Maximization/"
    FILENAME = "reverseCCWPrmaxL_%s.txt" %model
    ftime = "time2kCCWPrmaxL_%s.txt" %model

    best_S = []
    min_lenS = float("Inf")
    pool2algo = None
    pool2average = None

    length_to_coverage = {0:0}
    norm_parameters = dict()

    R2k = [[0, 0]]

    time2preprocess = time.time()
    print 'Preprocessing to find minimal size of CC...'
    min_size = float("Inf")
    # find min_size to select CC within
    for length_it in range(50):
        CC = findCC(G, Ep)
        L, sortedCC = findL(CC, T)
        LCC_size = sortedCC[L-1][0]
        if LCC_size < min_size:
            min_size = LCC_size
    print 'Min size:', min_size
    print 'Finished preprocessing in %s sec' %(time.time() - time2preprocess)

    if pool2algo == None:
        pool2algo = multiprocessing.Pool(processes=cpu)
    if pool2average == None:
        pool2average = multiprocessing.Pool(processes=cpu)

    time2map = time.time()
    print 'Start mapping...'
    result = pool2algo.map(mapReverseCCWP, ((G, Ep, T, min_size) for i in range(R))) # result is [(scores1, L1), (scores2, L2), ...]
    # result = map(mapReverseCCWP, range(R)) # result is [(scores1, L1), (scores2, L2), ...]
    print 'Finished mapping in %s sec' %(time.time() - time2map)

    time2reduce = time.time()
    print 'Start reducing scores...'
    scores = dict(zip(G.nodes(), [0]*len(G)))
    maxL = -1
    minL = float("Inf")
    avgL = 0
    for (Sc, L) in result:
        avgL += L/len(result)
        if L > maxL:
            maxL = L
        if L < minL:
            minL = L
        for (node, score) in Sc.iteritems():
            scores[node] += score
    print 'Finished reducing in %s sec' %(time.time() - time2reduce)
    print 'avgL', avgL
    print 'minL', minL
    print 'maxL', maxL

    time2select = time.time()
    print 'Start selecting seed set S...'

    # select first top-L nodes with penalization
    scores_copied = deepcopy(scores)
    S = []
    Coverages = {0:0}

    # add first nodes (can be minL, maxL, avgL, 1, etc.)
    for i in range(int(r*maxL)):
        updateScores(scores_copied, S, Ep)
    # calculate spread for top-L nodes
    time2Ts = time.time()
    Ts = pool2average.map(mapAvgSize, ((G, S, Ep, I) for i in range(4)))
    # Ts = map(mapAvgSize, [S]*4)
    coverage = sum(Ts)/len(Ts)
    Coverages[len(S)] = coverage
    time2coverage = time.time() - time2Ts
    print '|S|: %s --> %s nodes | %s sec' %(len(S), coverage, time2coverage)
    with open("plotdata/" + ftime, 'a+') as fp:
        print >>fp, r, len(S), time2coverage
    with open(DROPBOX + "plotdata/" + ftime, 'a+') as fp:
        print >>fp, r, len(S), time2coverage

    # find Low and High
    if coverage > T:
        Low = 0
        High = len(S)
    else:
        while coverage < T:
            Low = len(S)
            High = 2*Low
            while len(S) < High:
                updateScores(scores_copied, S, Ep)
            time2Ts = time.time()
            Ts = pool2average.map(mapAvgSize, ((G, S, Ep, I) for i in range(4)))
            # Ts = map(mapAvgSize, [S]*4)
            coverage = sum(Ts)/len(Ts)
            Coverages[len(S)] = coverage
            time2coverage = time.time() - time2Ts
            print '|S|: %s --> %s nodes | %s sec' %(len(S), coverage, time2coverage)
            with open("plotdata/" + ftime, 'a+') as fp:
                print >>fp, r, len(S), time2coverage
            with open(DROPBOX + "plotdata/" + ftime, 'a+') as fp:
                print >>fp, r, len(S), time2coverage

    # find boundary using binary search
    lastS = deepcopy(S) # S gives us solution for k = 1..len(S)
    while Low + 1 != High:
        time2double = time.time()
        new_length = Low + (High - Low)//2
        lastS = S[:new_length]
        time2Ts = time.time()
        Ts = pool2average.map(mapAvgSize, ((G, lastS, Ep, I) for i in range(4)))
        # Ts = map(mapAvgSize, [lastS]*4)
        coverage = sum(Ts)/len(Ts)
        Coverages[new_length] = coverage
        time2coverage = time.time() - time2Ts
        print '|S|: %s --> %s nodes | %s sec' %(len(lastS), coverage, time2coverage)
        with open("plotdata/" + ftime, 'a+') as fp:
            print >>fp, r, len(lastS), time2coverage
        with open(DROPBOX + "plotdata/" + ftime, 'a+') as fp:
            print >>fp, r, len(lastS), time2coverage

        if coverage < T:
            Low = new_length
        else:
            High = new_length

    assert Coverages[Low] < T
    assert Coverages[High] >= T
    finalS = S[:High]
    R2k.append([R, High])
    # with open('plotdata/' + FILENAME, 'w+') as fp:
    #     print >>fp, T
    #     json.dump(R2k, fp)
    # with open(DROPBOX + 'plotdata/' + FILENAME, 'w+') as fp:
    #     print >>fp, T
    #     json.dump(R2k, fp)

    # with open('plotdata/' + FILENAME, 'a+') as fp:
    #     print >>fp, updatef, High
    # with open(DROPBOX + 'plotdata/' + FILENAME, 'a+') as fp:
    #     print >>fp, updatef, High

    print finalS
    print "Number of binary steps:", len(Coverages) - 1
    print 'Necessary %s initial nodes to target %s nodes in graph G' %(len(finalS), T)
    with open('plotdata/' + FILENAME, 'a+') as fp:
        print >>fp, r, T, High
    with open(DROPBOX + 'plotdata/' + FILENAME, 'a+') as fp:
        print >>fp, r, T, High
    with open("plotdata/BinaryStepsCCWPrmaxL_%s.txt" %model, 'a+') as fp:
        print >>fp, r, T, len(Coverages) - 1
    with open(DROPBOX + "plotdata/BinaryStepsCCWPrmaxL_%s.txt" %model, 'a+') as fp:
        print >>fp, r, T, len(Coverages) - 1


    print 'Finished selecting seed set S in %s sec' %(time.time() - time2select)
    print '----------------------------------------------'
    # with open("plotdata/timeReverseCCWPforReverse3.txt", "w+") as fp:
    #     fp.write("%s" %(time.time() - time2select))
    #
    # with open("plotdata/rawCCWPforDirect2.txt", "a+") as f:
    #     json.dump({T: finalS}, f)
    #     print >>f
    #
    # with open("plotdata/rawCCWPTimeforDirect2.txt", "a+") as f:
    #     json.dump({T: time.time() - start}, f)
    #     print >>f
    #
    # # map length: [0,len(S)] to coverage
    # print 'Start estimating coverages...'
    # step = 5
    # for length in range(1, len(finalS)+1, step):
    #     if length in Coverages:
    #         norm_parameters[length] = norm_parameters.get(length,0) + 1
    #         length_to_coverage[length] = length_to_coverage.get(length, 0) + Coverages[length]
    #         print '|S|: %s --> %s' %(length, Coverages[length])
    #     else:
    #         norm_parameters[length] = norm_parameters.get(length,0) + 1
    #         # calculate coverage
    #         Ts = pool2average.map(mapAvgSize, [finalS[:length]]*4)
    #         coverage = sum(Ts)/len(Ts)
    #         length_to_coverage[length] = length_to_coverage.get(length, 0) + coverage
    #         print '|S|: %s --> %s' %(length, coverage)
    #
    # # if we haven't added result for T then add it
    # if (len(finalS) - 1)%step != 0:
    #     norm_parameters[len(finalS)] = norm_parameters.get(len(finalS),0) + 1
    #     length_to_coverage[len(finalS)] = length_to_coverage.get(len(finalS), 0) + Coverages[len(finalS)]
    #     print '|S|: %s --> %s' %(len(finalS), Coverages[len(finalS)])
    #
    # # normalizing coverages
    # for length in norm_parameters:
    #     length_to_coverage[length] /= norm_parameters[length]
    #
    # length_to_coverage = sorted(length_to_coverage.iteritems(), key = lambda (dk, dv): dk)
    #
    # with open("plotdata/plotReverseCCWPforReverse3.txt", "w+") as fp:
    #     json.dump(length_to_coverage, fp)

    print 'Total time: %s sec' %(time.time() - start)

    console = []
