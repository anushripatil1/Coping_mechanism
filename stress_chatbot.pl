:- use_module(library(csv)).
:- use_module(library(readutil)).
:- use_module(library(lists)).

% Facts to store student data
:- dynamic student/20.

% Load data from CSV
load_data :-
    csv_read_file('Student_Mental_Stress_and_Coping_Mechanisms.csv', Rows, [functor(student)]),
    maplist(assert, Rows).

% Helper predicates
get_stress_level(StudentID, Level) :-
    student(StudentID, _, _, _, _, _, _, _, _, _, _, _, Level, _, _, _, _, _, _, _).

get_coping_mechanism(StudentID, Mechanism) :-
    student(StudentID, _, _, _, _, _, _, _, _, _, _, _, _, _, _, Mechanism, _, _, _, _).

% Rules for stress analysis
high_stress(StudentID) :-
    get_stress_level(StudentID, Level),
    Level >= 7.

medium_stress(StudentID) :-
    get_stress_level(StudentID, Level),
    Level >= 4,
    Level < 7.

low_stress(StudentID) :-
    get_stress_level(StudentID, Level),
    Level < 4.

% Rules for coping mechanism effectiveness
effective_coping(Mechanism) :-
    findall(Stress, (student(_, _, _, _, _, _, _, _, _, _, _, _, Stress, _, _, Mechanism, _, _, _, _), Stress < 5), Stresses),
    length(Stresses, Count),
    Count > 10.

% Rules for recommendations
recommend_coping(StressLevel, Mechanism) :-
    StressLevel >= 7,
    member(Mechanism, ['Meditation', 'Yoga', 'Counseling']).

recommend_coping(StressLevel, Mechanism) :-
    StressLevel >= 4,
    StressLevel < 7,
    member(Mechanism, ['Exercise', 'Talking to Friends', 'Reading']).

recommend_coping(StressLevel, Mechanism) :-
    StressLevel < 4,
    member(Mechanism, ['Walking or Nature Walks', 'Social Media Engagement']).

% Chatbot interface
start_chatbot :-
    write('Welcome to the Student Stress Analysis Chatbot!'), nl,
    write('Type "quit" to exit.'), nl,
    write('Type "help" for available commands.'), nl,
    chat_loop.

chat_loop :-
    write('> '),
    read_line_to_string(user_input, Input),
    (Input = "quit" -> 
        write('Goodbye!'), nl
    ; Input = "help" ->
        show_help,
        chat_loop
    ; Input = "load" ->
        load_data,
        write('Data loaded successfully!'), nl,
        chat_loop
    ; Input = "analyze" ->
        analyze_stress,
        chat_loop
    ; Input = "recommend" ->
        get_recommendation,
        chat_loop
    ; otherwise ->
        write('Unknown command. Type "help" for available commands.'), nl,
        chat_loop
    ).

show_help :-
    write('Available commands:'), nl,
    write('  load    - Load student stress data'), nl,
    write('  analyze - Analyze stress levels'), nl,
    write('  recommend - Get coping mechanism recommendations'), nl,
    write('  help    - Show this help message'), nl,
    write('  quit    - Exit the chatbot'), nl.

analyze_stress :-
    write('Enter student ID: '),
    read_line_to_string(user_input, StudentID),
    (student(StudentID, _, _, _, _, _, _, _, _, _, _, _, Stress, _, _, Mechanism, _, _, _, _) ->
        write('Student ID: '), write(StudentID), nl,
        write('Stress Level: '), write(Stress), nl,
        write('Current Coping Mechanism: '), write(Mechanism), nl,
        (high_stress(StudentID) -> write('High stress level detected!'), nl
        ; medium_stress(StudentID) -> write('Medium stress level detected.'), nl
        ; low_stress(StudentID) -> write('Low stress level detected.'), nl
        )
    ; write('Student not found!'), nl
    ).

get_recommendation :-
    write('Enter stress level (1-10): '),
    read_line_to_string(user_input, StressStr),
    atom_number(StressStr, Stress),
    write('Recommended coping mechanisms:'), nl,
    findall(M, recommend_coping(Stress, M), Mechanisms),
    list_to_set(Mechanisms, UniqueMechanisms),
    maplist(write_recommendation, UniqueMechanisms).

write_recommendation(Mechanism) :-
    write('- '), write(Mechanism), nl. 