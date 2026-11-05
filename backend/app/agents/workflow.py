from typing import TypedDict
from langgraph.graph import StateGraph, END
from app.models import AgentExecution, RecoveryPlan
from app.services.simulation import uid

AGENTS=[('Monitoring Agent','Observe inventory, orders and transport events'),('Disruption Detection Agent','Classify exceptions and affected nodes'),('Demand Forecasting Agent','Estimate stock requirements from daily demand'),('Risk Assessment Agent','Score probability × operational impact'),('Digital Twin Simulation Agent','Trace downstream dependencies and exposure'),('Recovery Planning Agent','Compare four recovery strategies'),('Decision Agent','Select a plan for human approval'),('Execution Agent','Apply approved simulated actions'),('Reporting Agent','Record outcomes and recovery performance')]
class State(TypedDict):
    result: dict
    completed: list

def run_workflow(db,result,disruption,strategies):
    graph=StateGraph(State)
    previous=None
    for name,_ in AGENTS[:7]:
        def step(state,name=name):
            output={'message':f'{name} completed using persisted supply chain data','risk':result['risk_after'],'affected_nodes':len(result['affected_nodes']),'simulated':True}
            db.add(AgentExecution(id=uid('AGT'),agent=name,status='Completed',output=output))
            return {'result':state['result'],'completed':state['completed']+[name]}
        graph.add_node(name,step)
        if previous: graph.add_edge(previous,name)
        else: graph.set_entry_point(name)
        previous=name
    graph.add_edge(previous,END)
    graph.compile().invoke({'result':result,'completed':[]})
    best=min(strategies,key=lambda s:s['cost']*.0001+s['recovery_hours']*.4+(100-s['fulfillment'])*2)
    db.add(RecoveryPlan(id=uid('RCP'),disruption_id=disruption.id,strategy=best['strategy'],cost=best['cost'],recovery_hours=best['recovery_hours'],fulfillment=best['fulfillment'],confidence=90,status='Pending approval',data={**result,'required_inventory':result['shortage'],'mode':'Rule-based','confidence_note':'Heuristic score, not calibrated model probability'}))
    db.add(AgentExecution(id=uid('AGT'),agent='Execution Agent',status='Waiting for approval',output={'disruption_id':disruption.id,'simulated':True}))
