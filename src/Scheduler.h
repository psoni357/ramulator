/***************************** SCHEDULER.H ***********************************
- SAFARI GROUP

This file contains the different scheduling policies and row policies that the 
memory controller can use to schedule requests.

Current Memory Scheduling Policies:

1) FCFS - First Come First Serve
        This scheduling policy schedules memory requests chronologically

2) FRFCFS - Frist Ready First Come First Serve
        This scheduling policy first checks if a request is READY(meets all 
        timing parameters), if yes then it is prioritized. If multiple requests
        are ready, they they are scheduled chronologically. Otherwise, it 
        behaves the same way as FCFS. 

3) FRFCFS_Cap - First Ready First Come First Serve Cap
       This scheduling policy behaves the same way as FRFCS, except that it has
       a cap on the number of hits you can get in a certain row. The CAP VALUE
       can be altered by changing the number for the "cap" variable in 
       line number 76. 

4) FRFCFS_PriorHit - First Ready First Come First Serve Prioritize Hits
       This scheduling policy behaves the same way as FRFCFS, except that it
       prioritizes row hits more than readiness. 

You can select which scheduler you want to use by changing the value of 
"type" variable on line number 74.

                _______________________________________

Current Row Policies:

1) Closed   - Precharges a row as soon as there are no pending references to 
              the active row.
2) ClosedAP - Closed Auto Precharge
3) Opened   - Precharges a row only if there are pending references to 
              other rows.
4) Timeout  - Precharges a row after X time if there are no pending references.
              'X' time can be changed by changing the variable timeout 
              on line number 221

*****************************************************************************/

#ifndef __SCHEDULER_H
#define __SCHEDULER_H

#include "DRAM.h"
#include "Request.h"
#include "Controller.h"
#include <vector>
#include <map>
#include <list>
#include <functional>
#include <cassert>
#include <set>
extern uint64_t g_num_cycles;
extern uint64_t core_0_blacklist_count;
extern uint64_t core_1_blacklist_count;
extern uint64_t core_2_blacklist_count;
extern uint64_t core_3_blacklist_count;
using namespace std;

namespace ramulator
{

template <typename T>
class Controller;

template <typename T>
class Scheduler
{
public:
    Controller<T>* ctrl;

    enum class Type {
        FCFS, FRFCFS, FRFCFS_Cap, FRFCFS_PriorHit, BLISS, MAX
    } type = Type::FRFCFS; //Change this line to change scheduling policy

    long cap = 16; //Change  line to change cap
    //BLISS variables/constants
    int last_req_id = -1; //coreid of last recieved request, for BLISS policy
    int num_consec_reqs = 0; //number of consecutive requests from last_req_id
    int blacklist_thresh = 4; //number of consecutive requests before coreid is blacklisted
    std::set<int> blacklist_ids; //set of coreids that are blacklisted due to reaching the threshold
    int reset_time = 10000; //number of cycles before the blacklist set is cleared

    u_int64_t last_cycle = 0; //last cycle seen by scheduler - compare to see if difference is > reset_time
    
    Scheduler(Controller<T>* ctrl) : ctrl(ctrl) {}

    list<Request>::iterator get_head(list<Request>& q)
    {
        // TODO make the decision at compile time
        if (type != Type::FRFCFS_PriorHit) {
            //If queue is empty, return end of queue
            if (!q.size())
                return q.end();

            //Else return based on the policy
            auto head = q.begin();
            for (auto itr = next(q.begin(), 1); itr != q.end(); itr++)
                head = compare[int(type)](head, itr);

            return head;
        } 
        else { //Code to get around edge cases for FRFCFS_PriorHit
            
       //If queue is empty, return end of queue
            if (!q.size())
                return q.end();

       //Else return based on FRFCFS_PriorHit Scheduling Policy
            auto head = q.begin();
            for (auto itr = next(q.begin(), 1); itr != q.end(); itr++) {
                head = compare[int(Type::FRFCFS_PriorHit)](head, itr);
            }

            if (this->ctrl->is_ready(head) && this->ctrl->is_row_hit(head)) {
                return head;
            }

            // prepare a list of hit request
            vector<vector<int>> hit_reqs;
            for (auto itr = q.begin() ; itr != q.end() ; ++itr) {
                if (this->ctrl->is_row_hit(itr)) {
                    auto begin = itr->addr_vec.begin();
                    // TODO Here it assumes all DRAM standards use PRE to close a row
                    // It's better to make it more general.
                    auto end = begin + int(ctrl->channel->spec->scope[int(T::Command::PRE)]) + 1;
                    vector<int> rowgroup(begin, end); // bank or subarray
                    hit_reqs.push_back(rowgroup);
                }
            }
            // if we can't find proper request, we need to return q.end(),
            // so that no command will be scheduled
            head = q.end();
            for (auto itr = q.begin(); itr != q.end(); itr++) {
                bool violate_hit = false;
                if ((!this->ctrl->is_row_hit(itr)) && this->ctrl->is_row_open(itr)) {
                    // so the next instruction to be scheduled is PRE, might violate hit
                    auto begin = itr->addr_vec.begin();
                    // TODO Here it assumes all DRAM standards use PRE to close a row
                    // It's better to make it more general.
                    auto end = begin + int(ctrl->channel->spec->scope[int(T::Command::PRE)]) + 1;
                    vector<int> rowgroup(begin, end); // bank or subarray
                    for (const auto& hit_req_rowgroup : hit_reqs) {
                        if (rowgroup == hit_req_rowgroup) {
                            violate_hit = true;
                            break;
                        }  
                    }
                }
                if (violate_hit) {
                    continue;
                }
                // If it comes here, that means it won't violate any hit request
                if (head == q.end()) {
                    head = itr;
                } else {
                    head = compare[int(Type::FRFCFS)](head, itr);
                }
            }

            return head;
        }
    }

//Compare functions for each memory schedulers
private:
    void update_blacklist_and_count(int req_coreid){
        //Given a to-be-returned req core id,
        //updates the blacklist, last_req_id, and num_consec_reqs

        //First check if consecutive, if so update, else reset. 
        this->num_consec_reqs = (req_coreid == this->last_req_id) ? this->num_consec_reqs + 1 : 0; 
        if(this->num_consec_reqs == 0){
            //reset
            this->last_req_id = req_coreid; 
        }

        //check if have to blacklist according to blacklist_thresh
        if(num_consec_reqs > blacklist_thresh && g_num_cycles!=0){
            //last_req_id had more than blacklist_thresh consecutive requests --> blacklist it
            //(if it's not already blacklisted)
            blacklist_ids.insert(req_coreid);

            if(req_coreid==0){
                core_0_blacklist_count++;
            }
            else if(req_coreid==1){
                core_1_blacklist_count++;
            }
            else if(req_coreid==2){
                core_2_blacklist_count++;
            }
            else if(req_coreid==3){
                core_3_blacklist_count++;
            }

            //printf("Added core to blacklist %d. Blacklisted cores:\n", req_coreid);
            //for(std::set<int>::iterator it=blacklist_ids.begin(); it!=blacklist_ids.end(); ++it){
            //    printf("Core: %d\n", *it);
            //}
        }
        
    }
    typedef list<Request>::iterator ReqIter;
    function<ReqIter(ReqIter, ReqIter)> compare[int(Type::MAX)] = {
        // FCFS
        [this] (ReqIter req1, ReqIter req2) {
            if (req1->arrive <= req2->arrive) return req1;
            return req2;},

        // FRFCFS
        [this] (ReqIter req1, ReqIter req2) {
            bool ready1 = this->ctrl->is_ready(req1);
            bool ready2 = this->ctrl->is_ready(req2);

            if (ready1 ^ ready2) {
                if (ready1) return req1;
                return req2;
            }

            if (req1->arrive <= req2->arrive) return req1;
            return req2;},

        // FRFCFS_CAP
        [this] (ReqIter req1, ReqIter req2) {
            bool ready1 = this->ctrl->is_ready(req1);
            bool ready2 = this->ctrl->is_ready(req2);

            ready1 = ready1 && (this->ctrl->rowtable->get_hits(req1->addr_vec) <= this->cap);
            ready2 = ready2 && (this->ctrl->rowtable->get_hits(req2->addr_vec) <= this->cap);

            if (ready1 ^ ready2) {
                if (ready1) return req1;
                return req2;
            }

            if (req1->arrive <= req2->arrive) return req1;
            return req2;},
        // FRFCFS_PriorHit
        [this] (ReqIter req1, ReqIter req2) {
            bool ready1 = this->ctrl->is_ready(req1) && this->ctrl->is_row_hit(req1);
            bool ready2 = this->ctrl->is_ready(req2) && this->ctrl->is_row_hit(req2);

            if (ready1 ^ ready2) {
                if (ready1) return req1;
                return req2;
            }

            if (req1->arrive <= req2->arrive) return req1;
            return req2;},
        //BLISS
        [this] (ReqIter req1, ReqIter req2) {
            //First check if blacklist needs to be cleared according g_num_cycles and reset_time
            u_int64_t cycle_difference = g_num_cycles - last_cycle;
            if(cycle_difference > this->reset_time){
                this->blacklist_ids.clear();
                last_cycle = g_num_cycles;
                //printf("\nClearing out blacklist.\n"); 
            }
            //Priority 1: Prioritize non-blacklisted
            //Check if either request is blacklisted
            bool req1_blacklisted = (this->blacklist_ids.count(req1->coreid) != 0);
            bool req2_blacklisted = (this->blacklist_ids.count(req2->coreid) != 0);
            
            if(req1_blacklisted ^ req2_blacklisted){
                if(req1_blacklisted){
                    update_blacklist_and_count(req2->coreid);
                    return req2;
                }
                else{
                    update_blacklist_and_count(req1->coreid);
                    return req1;
                }
            }
            //Priority 2: Prioritize row-hit over non-hit
            bool req1_row_hit = this->ctrl->is_row_hit(req1);
            bool req2_row_hit = this->ctrl->is_row_hit(req2);

            if(req1_row_hit ^ req2_row_hit){
                if(req1_row_hit){
                    update_blacklist_and_count(req1->coreid);
                    return req1;
                }
                else{
                    update_blacklist_and_count(req2->coreid);
                    return req2; 
                }
            }

            //Priority 3: Prioritize older requests over younger requests 
            if (req1->arrive <= req2->arrive) {
                update_blacklist_and_count(req1->coreid);
                return req1; 
            } 
            else{
                update_blacklist_and_count(req2->coreid);
                return req2;
            }
        }
    };
};


// Row Precharge Policy
template <typename T>
class RowPolicy
{
public:
    Controller<T>* ctrl;

    enum class Type {
        Closed, ClosedAP, Opened, Timeout, MAX
    } type = Type::Opened;

    int timeout = 50;

    RowPolicy(Controller<T>* ctrl) : ctrl(ctrl) {}

    vector<int> get_victim(typename T::Command cmd)
    {
        return policy[int(type)](cmd);
    }

private:
    function<vector<int>(typename T::Command)> policy[int(Type::MAX)] = {
        // Closed
        [this] (typename T::Command cmd) -> vector<int> {
            for (auto& kv : this->ctrl->rowtable->table) {
                if (!this->ctrl->is_ready(cmd, kv.first))
                    continue;
                return kv.first;
            }
            return vector<int>();},

        // ClosedAP
        [this] (typename T::Command cmd) -> vector<int> {
            for (auto& kv : this->ctrl->rowtable->table) {
                if (!this->ctrl->is_ready(cmd, kv.first))
                    continue;
                return kv.first;
            }
            return vector<int>();},

        // Opened
        [this] (typename T::Command cmd) {
            return vector<int>();},

        // Timeout
        [this] (typename T::Command cmd) -> vector<int> {
            for (auto& kv : this->ctrl->rowtable->table) {
                auto& entry = kv.second;
                if (this->ctrl->clk - entry.timestamp < timeout)
                    continue;
                if (!this->ctrl->is_ready(cmd, kv.first))
                    continue;
                return kv.first;
            }
            return vector<int>();}
    };

};


template <typename T>
class RowTable
{
public:
    Controller<T>* ctrl;

    struct Entry {
        int row;
        int hits;
        long timestamp;
    };

    map<vector<int>, Entry> table;

    RowTable(Controller<T>* ctrl) : ctrl(ctrl) {}

    void update(typename T::Command cmd, const vector<int>& addr_vec, long clk)
    {
        auto begin = addr_vec.begin();
        auto end = begin + int(T::Level::Row);
        vector<int> rowgroup(begin, end); // bank or subarray
        int row = *end;

        T* spec = ctrl->channel->spec;

        if (spec->is_opening(cmd))
            table.insert({rowgroup, {row, 0, clk}});

        if (spec->is_accessing(cmd)) {
            // we are accessing a row -- update its entry
            auto match = table.find(rowgroup);
            assert(match != table.end());
            assert(match->second.row == row);
            match->second.hits++;
            match->second.timestamp = clk;
        } /* accessing */

        if (spec->is_closing(cmd)) {
          // we are closing one or more rows -- remove their entries
          int n_rm = 0;
          int scope;
          if (spec->is_accessing(cmd))
            scope = int(T::Level::Row) - 1; //special condition for RDA and WRA
          else
            scope = int(spec->scope[int(cmd)]);

          for (auto it = table.begin(); it != table.end();) {
            if (equal(begin, begin + scope + 1, it->first.begin())) {
              n_rm++;
              it = table.erase(it);
            }
            else
              it++;
          }

          assert(n_rm > 0);
        } /* closing */
    }

    int get_hits(const vector<int>& addr_vec, const bool to_opened_row = false)
    {
        auto begin = addr_vec.begin();
        auto end = begin + int(T::Level::Row);

        vector<int> rowgroup(begin, end);
        int row = *end;

        auto itr = table.find(rowgroup);
        if (itr == table.end())
            return 0;

        if(!to_opened_row && (itr->second.row != row))
            return 0;

        return itr->second.hits;
    }

    int get_open_row(const vector<int>& addr_vec) {
        auto begin = addr_vec.begin();
        auto end = begin + int(T::Level::Row);

        vector<int> rowgroup(begin, end);

        auto itr = table.find(rowgroup);
        if(itr == table.end())
            return -1;

        return itr->second.row;
    }
};

} /*namespace ramulator*/

#endif /*__SCHEDULER_H*/
