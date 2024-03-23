# Context Free Grammar Normalization
## Automatically converting a CFG to Chomsky Normal Form

### Input Format
The input consists of a sequence of rules (rules can be split across lines).

Each rule is of the form `A -> B1 | B2 | ... | Bn ;;`,
where: 
- `A` is a non-terminal symbol, 
- `B1, B2, ..., Bn` are sequences of non-terminal and terminal symbols, and 
- `|` separate options within the RHS.
- `;;` is the rule terminator.

The LHS of the first rule is assumed to be the start symbol.

Example (a^i b^j where i != j):
```
S -> X | Y ;;
X -> a | aX | aXb ;;
Y -> b | Yb | aYb ;;
```

Note: user input may only contain one-letter symbols.

Note: the empty string is represented by `%`.

### Usage
Run `python cfgnorm.py -h` for usage and help.