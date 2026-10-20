pragma solidity ^0.8.18;

contract VoteContract {

    mapping(address => bool) private voters;
    mapping(address => bool) private hasVoted;

    bool public ended;
    bool public approved;

    uint public approvals;
    uint public rejections;
    uint public target;
    uint public voterCount;

    event VotingEnded(bool approved);
    event Vote(address voter, bool approved);

    modifier notEnded() {
        require(!ended, "Voting ended.");
        _;
    }

    constructor(address[] memory allowedVoters) {
        require(allowedVoters.length > 0, "No voters");
        require(allowedVoters.length % 2 == 1, "Even number of voters");
        voterCount = allowedVoters.length;
        target = allowedVoters.length / 2 + 1;
        for (uint i = 0; i < allowedVoters.length; i++) {
            voters[allowedVoters[i]] = true;
        }
    }

    function vote(bool approve) public notEnded {
        require(voters[msg.sender], "Invalid address.");
        require(!hasVoted[msg.sender], "You have already voted!");

        hasVoted[msg.sender] = true;

        if (approve) {
            approvals++;
            if (approvals >= target) {
                ended = true;
                approved = true;
                emit VotingEnded(true);
            }
        } else {
            rejections++;
            if (rejections >= target) {
                ended = true;
                approved = false;
                emit VotingEnded(false);
            }
        }
        emit Vote(msg.sender, approve);
    }

    function isApproved() public view returns(bool) {
        return approved;
    }
}