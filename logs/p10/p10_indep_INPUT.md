# INPUT for the independent CSPF programs (Phase 10 WP3b)

You are writing four packet-filter programs for a CSPF-style stack machine, from the description below only. Write them to /tmp/claude-1000/-home-mahim-bpf-repl/517b04c3-f7fd-4b71-a71b-1e66c7a44040/scratchpad/p10_indep/out/F1.sm, F2.sm, F3.sm, F4.sm.
RULES: use only this file and the check command given at the end. Do NOT read or list anything under /home/mahim/bpf-repl/src, /home/mahim/bpf-repl/build, /home/mahim/bpf-repl/logs, /home/mahim/bpf-repl/results or /home/mahim/bpf-repl/docs, and do not read any scripts/ file; do not search the web. Write your own programs; do not try to find existing ones.

## The four filters (Ethernet frames, DLT_EN10MB)

## 2. The four filters (Fig. 8 definitions, paper.txt L823-826)

Frames are Ethernet (DLT_EN10MB). Constants chosen by us (the paper's host names have no addresses): horse H = 10.0.0.10 (0x0A00 000A), gauguin G = 10.0.0.20 (0x0A00 0014); TCP ports finger 79, domain 53, login 513, shell 514 (`/etc/services`, `logs/p6c/p6c_services_grep.log`).

| id | paper definition | libpcap expression (oracle and BPF source) |
|---|---|---|
| F1 | IP packets | `ip` |
| F2 | IP packets with src or dst "horse" | `ip host 10.0.0.10` |
| F3 | TCP packets with src or dst port of finger, domain, login, or shell | `ip and tcp and (port 79 or port 53 or port 513 or port 514)` |

## The stack machine: opcodes and program file format

### 3.2 Stack machine (CSPF analogue), paper section 3.1
Interpreter `c1_eval_sm`: a stack of 16-bit elements in memory with a stack pointer, one `switch` over the opcode. Accept if the stack is empty or its top is non-zero at the end (paper.txt L295-296). Opcodes (our choices, D6c.3):

| opcode | action |
|---|---|
| `PUSHLIT k` | push literal k |
| `PUSHWORD n` | push the big-endian 16-bit packet word at byte offset n; if it does not lie wholly inside the packet push 0 |
| `PUSHIND` | pop a byte offset, push the 16-bit packet word there (0 if out of the packet): the indirection operator of paper.txt L705 |
| `PUSHIPIND n` | push the 16-bit word at byte offset 14 + 4*(byte14 & 0xf) + n (0 if out of the packet): a fused indirection that knows the IP header length, the **optimistic** CSPF for Filter 3 |
| `EQ NEQ AND OR XOR ADD LSH RSH` | pop b, pop a, push a op b (16-bit result; EQ and NEQ push 1 or 0) |
| `CAND` | pop a; if a == 0 stop with REJECT, else continue |
| `COR` | pop a; if a != 0 stop with ACCEPT, else continue |

M1 counts every executed opcode (a push and a binary operation are separate instructions, following the paper's wording at L341-343). Stack depth is limited to 32; overflow aborts.

Why out-of-range words read as 0 and do not terminate: with a tree that evaluates every leaf, a leaf that lies past the end of a short frame must not by itself reject a frame that the register machine accepts on an earlier leaf. The choice is ours; the paper only says CSPF "does not permit access to the last byte of an odd-length packet" (L400). Decision equivalence on short and truncated frames (section 6) tests the choice.


File format: one instruction per line, the opcode in capitals, followed by one decimal argument for PUSHLIT, PUSHWORD and PUSHIPIND (for example `PUSHWORD 12`, `PUSHLIT 2048`, `EQ`). No comments, no blank lines. A packet is accepted by the program if the stack is empty at the end or its top is non-zero, as the machine description says.

## Excerpts of the 1993 paper (docs/paper.txt, two-column text, lines L295-345, L395-407, L703-737)

```
packet. If the value of the function is true the kernel copies the                                                 of instructions. After evaluating a program, if the top of stack
packet for the application; if it is false the packet is ignored.                                                  has a non-zero value or the stack is empty then the packet is
   Historically there have been two approaches to the fil-                                                         accepted, otherwise it is rejected.
ter abstraction: a boolean expression tree (used by CSPF)                                                             There are two implementation shortcomings of the expres-
and a directed acyclic control flow graph or CFG (first used                                                       sion tree approach:6
by NNStat[1] and used by BPF). For example, Figure 4 il-
lustrates the two models with a filter that recognizes either
                                                                                                                       




                                                                                                                             The operand stack must be simulated. On most modern
IP or ARP packets on an Ethernet. In the tree model each                                                                     machines this means generating add and subtract opera-
node represents a boolean operation while the leaves repre-                                                                  tions to maintain a simulated stack pointer and actually
sent test predicates on packet fields. The edges represent                                                                   doing loads and stores to memory to simulate the stack.
operator-operand relationships. In the CFG model each node                                                                   Since memory tends to be the major bottleneck in mod-
represents a packet field predicate while the edges represent                                                                ern architectures, a filter model that can use values in
control transfers. The righthand branch is traversed if the                                                                  machine registers and avoid this memory traffic will be
predicate is true, the lefthand branch if false. There are two                                                               more efficient.
terminating leaves which represent true and false for the en-                                                          




                                                                                                                             The tree model often does unnecessary or redundant
tire filter.
                                                                                                                             computations. For example, the tree in fig. 4 will com-
   These two models of filtering are computationally equiv-
                                                                                                                             pute the value of ‘ether.type == ARP’ even if the test
alent. I.e., any filter that can be expressed in one can be
                                                                                                                             for IP is true. While this problem can be somewhat
expressed in the other. However, in implementation they are
                                                                                                                             mitigated by adding ‘short circuit’ operators to the filter
very different: The tree model maps naturally into code for a
                                                                                                                             machine, some inefficiency is intrinsic: Because of the
stack machine while the CFG model maps naturally into code
                                                                                                                           6 Note that it is not our intention to denigrate CSPF or its enormous
for a register machine. Since most modern machines are reg-
ister based, we will argue that the CFG approach lends itself                                                      contribution to the community — we simply wish to investigate the imple-
                                                                                                                   mentation implications of its filter model when run on modern hardware. The
to a more efficient implementation.                                                                                CSPF filtering mechanism was intended to support efficient protocol demul-
                                                                                                                   tiplexing for user-level network code. The initial implementation achieved
                                                                                                                   huge gains by performing user-specified demultiplexing inside the kernel
3.1 The CSPF (Tree) Model                                                                                          rather than in a user-process. After this, the incremental gain from a more
                                                                                                                   efficient filter design was negligible and, as a result, the designers of CSPF
The CSPF filter engine is based on an operand stack. In-                                                           invested less effort in the filter machinery and, indeed, have pointed out that
structions either push constants or packet data on the stack,                                                      the “filter language is not a result of careful analysis but rather embodies
or perform a binary boolean or bitwise operation on the top                                                        several accidents of history”[8].
Winter USENIX – Jan., 1993 – San Diego, CA                                                                                                  5

...
the CSPF model is restricted to a single sixteen bit data type
which results in a doubling of the number of operations to
manipulate 32 bit data such as Internet addresses or TCP se-                          Figure 5: CFG Filter Function for “host foo”.
quence numbers. Finally, the design does not permit access
                                                                                 For example, Figure 5 shows a CFG filter function that ac-
to the last byte of an odd-length packet.
                                                                              cepts all packets with an Internet address foo. We consider a
   While the CSPF model has shortcomings, it offers a novel                   scenario where the network layer protocols are IP, ARP, and
generalization of packet filtering: The idea of putting a                     Reverse ARP, all of which contain source and destination
pseudo-machine language interpreter in the kernel provides a                  Internet addresses. The filter should catch all cases. Accord-
   7 This graph reordering is, however, a non-trivial problem.   Our BPF      ingly, the link layer type field is tested first. In the case of
compiler (part of tcpdump[4]) contains a fairly sophisticated optimizer to    IP packets, the IP host address fields are queried, while in
reorder and minimize CFG filters. This optimizer is the subject of a future   the case of ARP packets, the ARP address fields are used.
...
kernel using iprof [9], an instruction count profiler. To fully
                                                                   language with high level string scanning primitives and rich
compare the two models, an indirection operator was added
                                                                   data structures. With the BPF extensions, it is well suited for
to CSPF so it could parse IP headers. The change was minor
                                                                   the rapid prototyping of networking analysis tools.
and did not adversely affect the original filtering performance.
                                                                      Netload and histo are two network visualization tools
Tests were run on large packet trace files gathered from a busy
                                                                   which produce real time network statistics on an X dis-
UC Berkeley campus network. Figure 8 shows the results for
four fairly typical filters.                                       play. Netload graphs utilization data in real time, using
                                                                   tcpdump style filter specifications. Histo produces a dynamic
   Filter 1 is trivial. It tests whether one 16 bit word in the
                                                                   interarrival-time histogram of timestamped multimedia net-
packet is a given value. The two models are fairly compara-
                                                                   work packets.
ble, with BPF faster by about 50%.
                                                                      The Reverse ARP daemon uses the BPF interface to read
   Filter 2 looks for a particular IP host (source or destina-     and write Reverse ARP requests and replies directly to the
tion) and shows more of a disparity—a performance gap of           local network. (We developed this program to allow us to
240%. The larger difference here is due mostly to the fact that    entirely replace NIT by BPF in our SunOS 4 systems. Each of
CSPF operates only on 16 bit words and needs two compar-           the Sun NIT-based applications (etherfind, traffic, and rarpd)
ison operations to determine the equality of a 32 bit Internet     now has a BPF analog.)
address.
                                                                      Finally, recent versions of NNStat[1] and nfswatch can be
   Filter 3 is an example of packet parsing (required to locate    configured to run over BPF (in addition to running over NIT).
the TCP destination port field) and illustrates a yet greater
performance gap. The BPF filter parses the packet once,
loading the port field into the accumulator then simply does a     5 Conclusion
comparison cascade of the interesting ports. The CSPF filter
must re-do the parse and relocate the TCP header for each          BPF has proven to be an efficient, extensible, and portable
port to be tested.                                                 interface for network monitoring. Our comparison studies
   Finally, filter 5 demonstrates the effect of the unnecessary    have shown that it outperforms NIT in its buffer manage-
computations done by CSPF for a filter similar to the one          ment and CSPF in its filtering mechanism. Its programmable
```

## How to check your programs

Run: `bash /home/mahim/bpf-repl/scripts/p10_c1_indep_check.sh /tmp/claude-1000/-home-mahim-bpf-repl/517b04c3-f7fd-4b71-a71b-1e66c7a44040/scratchpad/p10_indep/out`. It compares the decisions of your four programs with libpcap on four traces and prints only the number of mismatches per (trace, filter). Iterate until every line says 0 mismatches. It prints no cost figure and you must not try to measure one.
Programs should be natural for this machine as the paper describes it (a boolean expression tree evaluated on the operand stack, optionally with the short-circuit operators); do not optimize for any particular metric.
When done, report: the four files' contents, the last output of the check command, and a plain list of every file and directory you read or listed.

## ADDENDUM (second message; the first INPUT.md cut the table after F3 by a line-range mistake of mine)

| F4 | IP, ARP or RARP packets between hosts "horse" and "gauguin" | `host 10.0.0.10 and host 10.0.0.20` |

The oracle's semantics are the specification: F3 includes libpcap's "not a non-first IP fragment" test; F4 means (IP: one of src/dst is H and one of src/dst is G) or (ARP, RARP: sender or target protocol address is H, and sender or target is G). The CSPF programs must reproduce exactly these decisions (section 6).

ARP and RARP frames have Ethernet types 0x0806 and 0x8035; use your own knowledge of the ARP header layout for IPv4 over Ethernet.
