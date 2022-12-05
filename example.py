from time import sleep
from webworkStats import Problem, Webwork2Client

target = "https://webwork.xxxxxxxxxxx.xxxxx/course/"
c = Webwork2Client(target)
c.login("###user###", "###password###")
sections  = c.get_sections()
for section in sections:
    """
    this prints all non full marks problems in every section
    
    ```
    Section: 1
        problem 1, 1, 2
    ```
    
    """
    print(section.name)
    for problem in section.get_problems():
        problem : Problem
        if problem.percent_score == 100:
            continue
        if problem.remaining == 0:
            print(f"⛔", end="")
        
        print(f"\t{problem.name} {problem.remaining} {problem.actual_score}")
    sleep(2)
    