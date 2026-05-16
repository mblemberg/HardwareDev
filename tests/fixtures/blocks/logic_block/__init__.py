"""Worked-example logic block: a 2-to-4 decoder.

Demonstrates the truth-table flow: ``decoder_spec`` declares the spec from the
datasheet; ``decoder_actual`` computes what the implementation produces (here
just a function representing the circuit's logic); a `@verification_test`
asserts the two match exhaustively.
"""
