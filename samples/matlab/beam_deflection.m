function [delta, stress] = beam_deflection(load_N, length_m, E_Pa, I_m4)
% BEAM_DEFLECTION  Tip deflection and peak bending stress of a cantilever bracket.
%   [delta, stress] = beam_deflection(load_N, length_m, E_Pa, I_m4) returns the
%   tip deflection (m) and the maximum bending stress (Pa) for a point load at
%   the free end. Used to size the bracket_assembly mounting arm.
delta = load_N * length_m^3 / (3 * E_Pa * I_m4);
stress = load_N * length_m * section_c() / I_m4;
end

function c = section_c()
% Distance from neutral axis to outer fibre for the 10 mm plate (m).
c = 0.005;
end
